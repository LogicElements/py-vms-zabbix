"""Reads the BVMS database and computes the metric values from it.

What each metric is computed from is the source table of UC4 in the PRS. Values of
the info table are read by column name, never by position, so adding a column or
reordering the table does not change what is sent.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone, tzinfo

import mysql.connector
from mysql.connector import errorcode

from zabbixvms.config import DatabaseConfig, Turbine

# Columns of the info table the metrics are computed from. They are enumerated in the
# query instead of SELECT *, so every value is picked by name.
INFO_COLUMNS = (
    "Date",
    "Phase_Marker",
    "Date_Timestamp",
    "Date_Config",
    "Date_Buffer_1",
    "Date_Buffer_2",
    "Time_bulk_1",
    "Time_bulk_2",
)

# Ages are reported up to one month; anything older says the same thing, that the data
# stopped coming long ago. The database keeps 0001-01-01 for "never", which saturates
# here like any other very old date.
MAX_AGE = timedelta(days=30)
MAX_AGE_SECONDS = int(MAX_AGE.total_seconds())

# Metrics of a buffer the turbine does not have configured.
NO_BUFFER = 0

# Metrics of a turbine that has no raw data prefix configured.
NO_RAW_DATA = 0

# The date a raw data table carries at the end of its name, by its number of digits:
# TVMS starts a table every day, VMS every few hours.
RAW_DATE_FORMATS = {8: "%Y%m%d", 14: "%Y%m%d%H%M%S"}

# A raw data table nothing has been written to yet stands for a stopped write only once
# it is older than this. The system creates the table and writes into it a moment
# later, and a cycle of the agent can fall in between.
FRESH_RAW_TABLE = timedelta(minutes=1)


# The zone the time of the server is in, None for the one Windows is set to. Only tests
# put another one here.
LOCAL_ZONE: tzinfo | None = None

# PTimeStamp of the trend data table is a DATETIME on the servers, which the connector
# hands over as datetime; a table that keeps it as text writes it in this form.
TREND_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"


class CollectorError(Exception):
    """The database does not hold what the agent needs for a turbine."""


# Under this the turbine is standing. A standstill does not always leave the phase marker
# period empty: the electronics writes 2147483647, the largest a 32 bit number holds, and
# the computation turns that into 2.794 rpm. It is noise, not a turbine turning slowly.
MIN_SPEED = 3.0


def speed(phase_marker: int | None) -> float:
    """Turbine speed in rpm from the phase marker period.

    A standing turbine has no phase marker period, the speed is 0 rpm then, and so is
    anything the computation puts under MIN_SPEED.
    """
    if not phase_marker:
        return 0.0
    turning = round(1e8 / phase_marker * 60, 4)
    return turning if turning >= MIN_SPEED else 0.0


def age(moment: datetime | None, now: datetime) -> int:
    """Whole seconds between moment and the measurement time, at most one month.

    A missing value means the data never came, which is as old as it gets and
    saturates too. A date in the future would be a negative age, which an unsigned
    item cannot hold, so it reads as zero.
    """
    if moment is None:
        return MAX_AGE_SECONDS
    elapsed = int((now - moment).total_seconds())
    return max(0, min(elapsed, MAX_AGE_SECONDS))


@dataclass(frozen=True)
class RawTable:
    """One raw data table: when its name says it was started, and when it was
    really created and last written to, as information_schema knows it."""

    name: str
    created: datetime
    updated: datetime | None
    create_time: datetime | None


def raw_table_created(prefix: str, name: str) -> datetime | None:
    """Time in the name of a raw data table of that prefix, None for any other table.

    The whole name has to fit, <prefix>_<date>: a prefix that merely starts another one,
    btt_tg1 against btt_tg11_20260925120000, must not take its tables. Names are
    matched regardless of case, the way MySQL on Windows compares them.
    """
    digits = "|".join(rf"\d{{{length}}}" for length in RAW_DATE_FORMATS)
    match = re.fullmatch(rf"{re.escape(prefix)}_({digits})", name, re.IGNORECASE)
    if match is None:
        return None
    stamp = match.group(1)
    try:
        return datetime.strptime(stamp, RAW_DATE_FORMATS[len(stamp)])
    except ValueError:
        return None


def like_prefix(prefix: str) -> str:
    """LIKE pattern of the tables starting with the prefix and an underscore.

    An underscore is a wildcard to LIKE, so left alone it would let btt_tg1 match
    btt_tg11_...; the pattern only narrows the query, raw_table_created() decides.
    """
    return prefix.replace("\\", "\\\\").replace("_", "\\_").replace("%", "\\%") + "\\_%"


def last_write(table: RawTable | None, now: datetime) -> datetime | None:
    """When the table was last written to, as far as its write age goes.

    A table nothing has been written to yet has no UPDATE_TIME. Within FRESH_RAW_TABLE
    of its creation that is not a stopped write but the first rows still to come, so
    the creation stands in for a write; after that the table is as old as it gets.
    The creation is CREATE_TIME, not the date in the name: a TVMS table carries only
    its day, which says nothing of when in that day it came to be.
    """
    if table is None:
        return None
    if (table.updated is None and table.create_time is not None
            and now - table.create_time < FRESH_RAW_TABLE):
        return table.create_time
    return table.updated


@dataclass(frozen=True)
class TrendWindow:
    """What the newest rows of the trend data table say about a turbine's signals.

    last holds the newest PTimeStamp of each signal that has a row in the window, None
    for one that is not a time. oldest is the PTimeStamp of the first row of the window,
    None when the window is empty or that is not a time.
    """

    last: dict[int, datetime | None]
    oldest: datetime | None


def trend_timestamp(value: datetime | str | None,
                    utc_offset: int | None = None) -> datetime | None:
    """Time in a PTimeStamp of the trend data table as the clock of the server shows it,
    None for anything unreadable.

    The column is a DATETIME, which arrives as it is; text in the form of
    TREND_TIMESTAMP_FORMAT is read too, so a table that keeps the time as text
    works as well. The software that writes it stamps in UTC+1 all year, so with
    utc_offset the stamp is taken as a time in that fixed zone and turned into local
    time, which makes the summer time come out right: a constant added to the age would
    be an hour wrong in winter, and a stopped write would go unnoticed for that hour.
    """
    if not isinstance(value, datetime):
        try:
            value = datetime.strptime(value, TREND_TIMESTAMP_FORMAT)
        except (TypeError, ValueError):
            return None
    if utc_offset is None:
        return value
    try:
        stamped = value.replace(tzinfo=timezone(timedelta(hours=utc_offset)))
        return stamped.astimezone(LOCAL_ZONE).replace(tzinfo=None)
    except (OverflowError, OSError, ValueError):
        # 0001-01-01 is how "never" is written and has no local time to turn into.
        return None


def trend_age(signals: list[int], window: TrendWindow, now: datetime) -> int:
    """Age of the signal of the turbine that has gone quiet the longest.

    A signal with no row in the window has been quiet for at least as long as the window
    reaches back, which is all the query can say without reading the whole table; the
    first row of the window stands for it. An empty window and a time that cannot be
    read are as old as an age gets.
    """
    return max(
        (age(window.last.get(signal, window.oldest), now) for signal in signals),
        default=0,
    )


def trend_queries(table: str, signals: int) -> tuple[str, str]:
    """The two queries on the trend data table: the newest PTimeStamp of each of that
    many signals within the window, and the first PTimeStamp of the window.

    Parameters of both are the size of the window first, then the signals. The window
    is what lies above MAX(Id) less its size; MAX(Id) is read from the end of the
    primary key and the rest is a range of it.
    """
    quoted = "`" + table.replace("`", "``") + "`"
    in_window = f"`Id` > (SELECT MAX(`Id`) FROM {quoted}) - %s"
    placeholders = ", ".join(["%s"] * signals)
    last_query = (f"SELECT `SigID`, MAX(`PTimeStamp`) AS `LastWrite` FROM {quoted} "
                  f"WHERE {in_window} AND `SigID` IN ({placeholders}) "
                  f"GROUP BY `SigID`")
    oldest_query = (f"SELECT `PTimeStamp` FROM {quoted} WHERE {in_window} "
                    f"ORDER BY `Id` LIMIT 1")
    return last_query, oldest_query


def raw_values(raw_tables: dict[str, list[RawTable]], now: datetime) -> dict[str, int]:
    """Raw data metrics of one turbine, summed up over its prefixes as the worst one.

    Tables piling up under one prefix mean its export stopped, however few the other
    prefixes have, so the count is the largest of them; the same goes for the write
    age. Only the newest table of a prefix is written to, an older one waits for its
    export, so the write age is taken from the newest.
    """
    count = write_age = NO_RAW_DATA
    for tables in raw_tables.values():
        count = max(count, len(tables))
        newest = max(tables, key=lambda table: table.created, default=None)
        write_age = max(write_age, age(last_write(newest, now), now))
    return {"vms.raw_tables": count, "vms.raw_write_age": write_age}


class Collector:
    """Reads one turbine's values out of the BVMS database."""

    def __init__(self, database: DatabaseConfig, connect=mysql.connector.connect) -> None:
        self._database = database
        self._connect = connect
        self._connection = None
        # Things worth telling about that do not stop the collection; filled by
        # collect() for the turbine it was called with.
        self.warnings: list[str] = []
        # What stopped one value from being had while the rest was; the cycle goes on
        # with the others. Filled by collect() like warnings.
        self.errors: list[str] = []

    def connect(self) -> None:
        """Open the connection to MySQL using the values from the configuration."""
        self._connection = self._connect(
            host=self._database.host,
            database=self._database.database,
            user=self._database.user,
            password=self._database.password,
            # The bundled libmysql.dll is built with a toolset whose std::mutex needs
            # the Visual C++ runtime 14.40 or newer and faults with an access violation
            # on an older one, killing the process where no Python handler can see it.
            # The pure Python implementation never calls into libmysql, and a handful
            # of rows per period does not need the speed of the C extension.
            use_pure=True,
            # Every query has to see the database as it is now. The connector leaves
            # autocommit off, so the first query would open a transaction the agent,
            # only reading, never ends, and InnoDB would answer every later query from
            # the snapshot taken at its start. On MySQL 8 that goes for
            # information_schema too, whose tables are InnoDB: a raw data table created
            # since would stay unseen and a dropped one would still be counted.
            autocommit=True,
        )
        self._read_live_statistics()

    def _read_live_statistics(self) -> None:
        """Have information_schema read TABLE_ROWS and UPDATE_TIME from the engine.

        MySQL 8 answers them from a cache it refreshes after
        information_schema_stats_expiry seconds, a day unless set otherwise, so a
        raw data table being filled showed the write time of when it was first asked
        about. Zero makes this session read the engine on every query and leaves the
        server as it is. MySQL 5.7 has no such cache and does not know the variable.
        """
        cursor = self._connection.cursor(dictionary=True)
        try:
            cursor.execute("SET SESSION information_schema_stats_expiry = 0")
        except mysql.connector.Error as err:
            if err.errno != errorcode.ER_UNKNOWN_SYSTEM_VARIABLE:
                raise
        finally:
            cursor.close()

    @property
    def is_connected(self) -> bool:
        """Whether the collector currently holds a connection to MySQL."""
        return self._connection is not None

    def close(self) -> None:
        """Close the connection; closing a collector that is not connected is fine."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def read_info(self, turbine: Turbine) -> dict:
        """Row of the info table belonging to the turbine, keyed by column name."""
        columns = ", ".join(f"`{column}`" for column in INFO_COLUMNS)
        query = (f"SELECT {columns} FROM `{self._database.info_table}` "
                 f"WHERE `SystemId` = %s")

        cursor = self._cursor()
        try:
            cursor.execute(query, (turbine.system_id,))
            rows = cursor.fetchall()
        finally:
            cursor.close()

        if not rows:
            raise CollectorError(
                f"table {self._database.info_table} has no row with SystemId "
                f"{turbine.system_id}"
            )
        return rows[0]

    def read_buffer_rows(self, turbine: Turbine) -> dict[str, int]:
        """Row counts of the turbine's buffer tables, keyed by table name."""
        if not turbine.buffers:
            return {}

        placeholders = ", ".join(["%s"] * len(turbine.buffers))
        query = ("SELECT TABLE_NAME, TABLE_ROWS FROM information_schema.TABLES "
                 f"WHERE TABLE_SCHEMA = %s AND TABLE_NAME IN ({placeholders})")

        cursor = self._cursor()
        try:
            cursor.execute(query, (self._database.database, *turbine.buffers))
            rows = cursor.fetchall()
        finally:
            cursor.close()

        return {row["TABLE_NAME"]: row["TABLE_ROWS"] or 0 for row in rows}

    def read_raw_tables(self, turbine: Turbine) -> dict[str, list[RawTable]]:
        """Raw data tables of the turbine, keyed by prefix.

        Every configured prefix is a key, the ones without any table too: a prefix
        with nothing in the database is what the metrics are there to report.
        """
        if not turbine.raw_prefixes:
            return {}

        conditions = " OR ".join(["TABLE_NAME LIKE %s"] * len(turbine.raw_prefixes))
        query = ("SELECT TABLE_NAME, CREATE_TIME, UPDATE_TIME "
                 "FROM information_schema.TABLES "
                 f"WHERE TABLE_SCHEMA = %s AND ({conditions})")
        patterns = [like_prefix(prefix) for prefix in turbine.raw_prefixes]

        cursor = self._cursor()
        try:
            cursor.execute(query, (self._database.database, *patterns))
            rows = cursor.fetchall()
        finally:
            cursor.close()

        tables = {prefix: [] for prefix in turbine.raw_prefixes}
        for row in rows:
            for prefix in turbine.raw_prefixes:
                created = raw_table_created(prefix, row["TABLE_NAME"])
                if created is not None:
                    tables[prefix].append(RawTable(
                        row["TABLE_NAME"], created, row["UPDATE_TIME"],
                        row["CREATE_TIME"]))
        return tables

    def read_trend(self, turbine: Turbine) -> TrendWindow:
        """Newest PTimeStamp of each signal of the turbine within the newest rows of the
        trend data table.

        Id is the primary key and grows with the writing, so the newest trend_window rows
        are a range of it that begins at the end of the index: MAX(Id) is read from the
        index and nothing in the table is scanned behind that range. Looking a signal up
        over the whole table would read all of it exactly when the signal has stopped,
        which is what the metric is there for. Raises CollectorError when the table is
        not there.
        """
        last_query, oldest_query = trend_queries(
            self._database.trend_table, len(turbine.trend_signals))
        window = self._database.trend_window

        cursor = self._cursor()
        try:
            cursor.execute(last_query, (window, *turbine.trend_signals))
            last_rows = cursor.fetchall()
            cursor.execute(oldest_query, (window,))
            oldest_rows = cursor.fetchall()
        except mysql.connector.Error as err:
            if err.errno == errorcode.ER_NO_SUCH_TABLE:
                raise CollectorError(
                    f"trend table {self._database.trend_table} is not in database "
                    f"{self._database.database}") from err
            raise
        finally:
            cursor.close()

        offset = self._database.trend_utc_offset
        return TrendWindow(
            last={row["SigID"]: trend_timestamp(row["LastWrite"], offset)
                  for row in last_rows},
            oldest=(trend_timestamp(oldest_rows[0]["PTimeStamp"], offset)
                    if oldest_rows else None),
        )

    def collect(self, turbine: Turbine, now: datetime | None = None) -> dict[str, float]:
        """Values of all collected metrics of one turbine, keyed by metric key."""
        if now is None:
            now = datetime.now()
        self.warnings = []
        self.errors = []
        info = self.read_info(turbine)
        buffer_rows = self.read_buffer_rows(turbine)
        for table in turbine.buffers:
            if table not in buffer_rows:
                # Counting zero rows here would look like an empty buffer, which is
                # something else entirely than a table that is not there.
                self.warnings.append(
                    f"buffer table {table!r} is not in database {self._database.database}")
        raw_tables = self.read_raw_tables(turbine)
        # A turbine without signals asks the table nothing. A table that is not there
        # costs the turbine its trend age and nothing else: the other values do not
        # come from it, and withholding them would turn a mistake in the name of the
        # trend table into the silence of the whole turbine.
        trend = None
        if turbine.trend_signals:
            try:
                trend = self.read_trend(turbine)
            except CollectorError as err:
                self.errors.append(str(err))
        return self.values(turbine, info, buffer_rows, raw_tables, now, trend)

    @staticmethod
    def values(turbine: Turbine, info: dict, buffer_rows: dict[str, int],
               raw_tables: dict[str, list[RawTable]], now: datetime,
               trend: TrendWindow | None = None) -> dict[str, float]:
        """Metric values computed from one info row, the buffer row counts, the
        raw data tables and the window of the trend data.

        Every value of one cycle is computed against the same measurement time.
        """
        values = {
            "vms.speed": speed(info["Phase_Marker"]),
            "vms.info_age": age(info["Date"], now),
            "vms.timestamp_age": age(info["Date_Timestamp"], now),
            "vms.config_age": age(info["Date_Config"], now),
        }

        # The buffers are summed up into one metric each. Rows and bulk time add up;
        # the age is the worst of them, because summing two ages gives a number that
        # is the age of nothing. A buffer the turbine does not have contributes
        # nothing, so a turbine with one buffer reports exactly that one. Which info
        # columns a buffer uses follows its position, not the table name in the
        # configuration.
        rows = bulk = oldest = NO_BUFFER
        for index in (1, 2):
            if len(turbine.buffers) < index:
                continue
            table = turbine.buffers[index - 1]
            oldest = max(oldest, age(info[f"Date_Buffer_{index}"], now))
            bulk += info[f"Time_bulk_{index}"] or 0
            rows += buffer_rows.get(table, 0)

        values["vms.buf_rows"] = rows
        values["vms.buf_age"] = oldest
        values["vms.buf_bulk"] = bulk

        values.update(raw_values(raw_tables, now))

        # Only a turbine that has signals to watch has an age of them; zero would pass
        # for data that just arrived.
        if turbine.trend_signals and trend is not None:
            values["vms.trend_age"] = trend_age(turbine.trend_signals, trend, now)

        return values

    def _cursor(self):
        """Cursor returning rows as dicts, so values are picked by column name."""
        if self._connection is None:
            raise CollectorError("collector is not connected to the database")
        return self._connection.cursor(dictionary=True)
