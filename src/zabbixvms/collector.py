"""Reads the BVMS database and computes the metric values from it.

What each metric is computed from is the source table of UC4 in the PRS. Values of
the info table are read by column name, never by position, so adding a column or
reordering the table does not change what is sent.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import mysql.connector

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

# An age above this is nonsense (the database keeps 0001-01-01 for "never") and is
# reported as unavailable instead.
MAX_AGE = timedelta(days=1825)
UNAVAILABLE = -1

# Metrics of a buffer the turbine does not have configured.
NO_BUFFER = 0


class CollectorError(Exception):
    """The database does not hold what the agent needs for a turbine."""


def speed(phase_marker: int | None) -> float:
    """Turbine speed in rpm from the phase marker period.

    A standing turbine has no phase marker period, the speed is 0 rpm then.
    """
    if not phase_marker:
        return 0.0
    return round(1e8 / phase_marker * 60, 4)


def age(moment: datetime | None, now: datetime) -> int:
    """Whole seconds between moment and the measurement time.

    An age above five years, and a missing value, mean the datum is unavailable.
    """
    if moment is None:
        return UNAVAILABLE
    elapsed = now - moment
    if elapsed > MAX_AGE:
        return UNAVAILABLE
    return int(elapsed.total_seconds())


class Collector:
    """Reads one turbine's values out of the BVMS database."""

    def __init__(self, database: DatabaseConfig, connect=mysql.connector.connect) -> None:
        self._database = database
        self._connect = connect
        self._connection = None
        # Things worth telling about that do not stop the collection; filled by
        # collect() for the turbine it was called with.
        self.warnings: list[str] = []

    def connect(self) -> None:
        """Open the connection to MySQL using the values from the configuration."""
        self._connection = self._connect(
            host=self._database.host,
            database=self._database.database,
            user=self._database.user,
            password=self._database.password,
        )

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
                f"{turbine.system_id} of turbine {turbine.name!r}"
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

    def collect(self, turbine: Turbine, now: datetime | None = None) -> dict[str, float]:
        """Values of all collected metrics of one turbine, keyed by metric key."""
        if now is None:
            now = datetime.now()
        self.warnings = []
        info = self.read_info(turbine)
        buffer_rows = self.read_buffer_rows(turbine)
        for table in turbine.buffers:
            if table not in buffer_rows:
                # Counting zero rows here would look like an empty buffer, which is
                # something else entirely than a table that is not there.
                self.warnings.append(
                    f"buffer table {table!r} of turbine {turbine.name!r} is not in "
                    f"database {self._database.database}")
        return self.values(turbine, info, buffer_rows, now)

    @staticmethod
    def values(turbine: Turbine, info: dict, buffer_rows: dict[str, int],
               now: datetime) -> dict[str, float]:
        """Metric values computed from one info row and the buffer row counts.

        Every value of one cycle is computed against the same measurement time.
        """
        values = {
            "vms.speed": speed(info["Phase_Marker"]),
            "vms.info_age": age(info["Date"], now),
            "vms.timestamp_age": age(info["Date_Timestamp"], now),
            "vms.config_age": age(info["Date_Config"], now),
        }

        # Both buffers are always sent. Which info columns a buffer uses follows its
        # position, not the table name in the configuration.
        for index in (1, 2):
            if len(turbine.buffers) < index:
                values[f"vms.buf_age_{index}"] = NO_BUFFER
                values[f"vms.buf_bulk_{index}"] = NO_BUFFER
                values[f"vms.buf_rows_{index}"] = NO_BUFFER
                continue
            table = turbine.buffers[index - 1]
            values[f"vms.buf_age_{index}"] = age(info[f"Date_Buffer_{index}"], now)
            values[f"vms.buf_bulk_{index}"] = info[f"Time_bulk_{index}"] or 0
            values[f"vms.buf_rows_{index}"] = buffer_rows.get(table, 0)

        return values

    def _cursor(self):
        """Cursor returning rows as dicts, so values are picked by column name."""
        if self._connection is None:
            raise CollectorError("collector is not connected to the database")
        return self._connection.cursor(dictionary=True)
