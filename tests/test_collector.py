"""Tests of the collector against faked database objects: the computations of the
source table, the -1 limit, the zeros of an unconfigured buffer and the raw data tables
(UC4-R1, UC4-R2, UC4-R3, UC4-R4, UC4-R5, UC4-R7, UC4-R8, UC3-R3, UC6-R2,
UC6-R3, UC6-R4, UC6-R5)."""

import re
from datetime import datetime, timedelta

import mysql.connector
import pytest
from mysql.connector import errorcode

from zabbixvms import metrics
from zabbixvms.collector import (
    INFO_COLUMNS,
    MAX_AGE,
    MAX_AGE_SECONDS,
    MIN_SPEED,
    Collector,
    CollectorError,
    age,
    like_prefix,
    raw_table_created,
    speed,
)
from zabbixvms.config import DatabaseConfig, Turbine

NOW = datetime(2026, 9, 14, 12, 0, 0)


def vms_table(prefix, created):
    """Name of a VMS raw data table, which carries the time it was started."""
    return f"{prefix}_{created:%Y%m%d%H%M%S}"


def tvms_table(prefix, day):
    """Name of a TVMS raw data table, which carries only its day."""
    return f"{prefix}_{day:%Y%m%d}"


def like_regex(pattern):
    """The LIKE pattern as a regex, the way MySQL reads it: a backslash escapes, _ is
    one character, % any run of them, and case does not matter."""
    parts = []
    chars = iter(pattern)
    for char in chars:
        if char == "\\":
            parts.append(re.escape(next(chars)))
        elif char == "_":
            parts.append(".")
        elif char == "%":
            parts.append(".*")
        else:
            parts.append(re.escape(char))
    return re.compile("".join(parts), re.IGNORECASE | re.DOTALL)


def info_row(**overrides):
    """Info row as the dictionary cursor returns it, with sane values."""
    row = {
        "Date": NOW - timedelta(seconds=3),
        "Phase_Marker": 2000010,
        "Date_Timestamp": NOW - timedelta(seconds=5),
        "Date_Config": NOW - timedelta(seconds=7),
        "Date_Buffer_1": NOW - timedelta(seconds=11),
        "Date_Buffer_2": NOW - timedelta(seconds=13),
        "Time_bulk_1": 17,
        "Time_bulk_2": 19,
    }
    row.update(overrides)
    return row


class FakeCursor:
    """Cursor that answers the three queries of the collector from prepared rows."""

    def __init__(self, fake):
        self._fake = fake
        self._rows = []

    def execute(self, query, params=None):
        if query.startswith("SET "):
            # Settings of the session are kept apart from the queries for values.
            if self._fake.refuse_settings is not None:
                raise self._fake.refuse_settings
            self._fake.settings.append(query)
            return
        self._fake.executed.append((query, params))
        if " LIKE " in query:
            patterns = [like_regex(pattern) for pattern in params[1:]]
            self._rows = [
                {"TABLE_NAME": name, "UPDATE_TIME": updated,
                 "CREATE_TIME": self._fake.raw_created.get(name)}
                for name, updated in self._fake.raw_tables.items()
                if any(pattern.fullmatch(name) for pattern in patterns)
            ]
        elif "information_schema" in query:
            self._rows = [
                {"TABLE_NAME": name, "TABLE_ROWS": rows}
                for name, rows in self._fake.table_rows.items()
                if name in (params[1:] if params else ())
            ]
        else:
            self._rows = [row for row in self._fake.info_rows
                          if row["SystemId"] == params[0]]

    def fetchall(self):
        return [{key: value for key, value in row.items() if key != "SystemId"}
                for row in self._rows]

    def close(self):
        self._fake.closed_cursors += 1


class FakeConnection:
    def __init__(self, info_rows=(), table_rows=None, raw_tables=None,
                 raw_created=None, refuse_settings=None):
        self.info_rows = list(info_rows)
        self.table_rows = dict(table_rows or {})
        # Raw data tables by name, each with its UPDATE_TIME.
        self.raw_tables = dict(raw_tables or {})
        # CREATE_TIME of the raw data tables by name; a table left out has none.
        self.raw_created = dict(raw_created or {})
        # What a SET statement raises instead of taking effect, if anything.
        self.refuse_settings = refuse_settings
        self.settings = []
        self.executed = []
        self.closed_cursors = 0
        self.closed = False

    def cursor(self, dictionary=False):
        assert dictionary, "the collector must read values by column name"
        return FakeCursor(self)

    def close(self):
        self.closed = True


def make_collector(connection, info_table="info_le", database="BVMS"):
    config = DatabaseConfig(host="db", database=database, user="u", password="p",
                            info_table=info_table)
    collector = Collector(config, connect=lambda **kwargs: connection)
    collector.connect()
    return collector


def test_speed_from_the_phase_marker():
    """UC4-R1: vms.speed is 1e8 / Phase_Marker * 60."""
    assert speed(2000010) == round(1e8 / 2000010 * 60, 4)
    assert speed(10000140) == round(1e8 / 10000140 * 60, 4)


@pytest.mark.parametrize("phase_marker", [0, None])
def test_speed_of_a_standing_turbine_is_zero(phase_marker):
    """A turbine that does not turn has no phase marker period."""
    assert speed(phase_marker) == 0.0


def test_a_speed_under_the_floor_is_zero():
    """UC4-R1: the phase marker ticks even at a standstill, and what that yields is
    noise; below MIN_SPEED it is reported as a turbine that does not turn."""
    slow = int(1e8 * 60 / (MIN_SPEED / 2))

    assert 0 < 1e8 / slow * 60 < MIN_SPEED, "the fixture has to be under the floor"
    assert speed(slow) == 0.0


def test_the_floor_itself_still_counts_as_turning():
    """UC4-R1: only a speed under the floor is flattened, the floor is a real value."""
    at_the_floor = int(1e8 * 60 / MIN_SPEED)

    assert speed(at_the_floor) == MIN_SPEED


def test_age_is_whole_seconds():
    """UC4-R4: an age is the whole seconds against the measurement time."""
    assert age(NOW - timedelta(seconds=42), NOW) == 42
    assert age(NOW - timedelta(seconds=42, milliseconds=800), NOW) == 42


def test_age_at_the_limit_is_reported_as_it_is():
    """UC4-R4: exactly one month is still a computed value."""
    assert age(NOW - MAX_AGE, NOW) == MAX_AGE_SECONDS
    assert MAX_AGE == timedelta(days=30)


def test_age_above_one_month_saturates():
    """UC4-R4: older data says the same thing, so it is reported as one month."""
    assert age(NOW - MAX_AGE - timedelta(seconds=1), NOW) == MAX_AGE_SECONDS
    assert age(NOW - timedelta(days=365), NOW) == MAX_AGE_SECONDS
    # The database writes this date for "never".
    assert age(datetime(1, 1, 1), NOW) == MAX_AGE_SECONDS


def test_age_of_a_missing_value_is_the_oldest_there_is():
    """UC4-R4: no date means the data never came, which saturates as well."""
    assert age(None, NOW) == MAX_AGE_SECONDS


def test_age_of_a_date_in_the_future_is_zero():
    """UC4-R4: an unsigned item could not hold a negative age."""
    assert age(NOW + timedelta(seconds=30), NOW) == 0


def test_no_age_is_ever_negative():
    """UC4-R4: Zabbix would refuse a negative value on an unsigned item."""
    for moment in (None, datetime(1, 1, 1), NOW, NOW + timedelta(days=1),
                   NOW - timedelta(days=90)):
        assert age(moment, NOW) >= 0


def test_collected_keys_match_the_catalog():
    """UC3-R1: the collector fills exactly the keys of the catalog it owns."""
    turbine = Turbine(name="TG1", system_id=11, buffers=["buffer_le"])
    connection = FakeConnection(info_rows=[info_row(SystemId=11)],
                                table_rows={"buffer_le": 157062})

    values = make_collector(connection).collect(turbine, NOW)

    assert set(values) == set(metrics.COLLECTOR_KEYS)


def test_values_follow_the_source_table():
    """UC4-R1: every value comes from the field the source table names."""
    turbine = Turbine(name="TG1", system_id=11, buffers=["buffer_le", "buffer_le_3"])
    connection = FakeConnection(info_rows=[info_row(SystemId=11)],
                                table_rows={"buffer_le": 157062, "buffer_le_3": 58043})

    values = make_collector(connection).collect(turbine, NOW)

    assert values["vms.speed"] == round(1e8 / 2000010 * 60, 4)
    assert values["vms.info_age"] == 3
    assert values["vms.timestamp_age"] == 5
    assert values["vms.config_age"] == 7
    # Ages 11 and 13, bulk 17 and 19, rows 157062 and 58043 over the two buffers.
    assert values["vms.buf_age"] == 13
    assert values["vms.buf_bulk"] == 36
    assert values["vms.buf_rows"] == 215105


def test_one_cycle_uses_a_single_measurement_time():
    """UC4-R4: all metrics of a turbine are computed against the same time."""
    turbine = Turbine(name="TG1", system_id=11, buffers=[])
    row = info_row(SystemId=11, Date=NOW - timedelta(seconds=1),
                   Date_Timestamp=NOW - timedelta(seconds=1),
                   Date_Config=NOW - timedelta(seconds=1))
    connection = FakeConnection(info_rows=[row])

    values = make_collector(connection).collect(turbine, NOW)

    assert values["vms.info_age"] == values["vms.timestamp_age"] == 1
    assert values["vms.config_age"] == 1


def test_one_buffer_reports_exactly_that_one():
    """UC3-R3: a buffer the turbine does not have adds nothing to the sums."""
    turbine = Turbine(name="TG1", system_id=11, buffers=["buffer_le"])
    connection = FakeConnection(info_rows=[info_row(SystemId=11)],
                                table_rows={"buffer_le": 157062})

    values = make_collector(connection).collect(turbine, NOW)

    assert values["vms.buf_rows"] == 157062
    assert values["vms.buf_age"] == 11
    assert values["vms.buf_bulk"] == 17


def test_age_is_the_worst_of_the_buffers_not_their_sum():
    """UC4-R5: two ages added up would be the age of nothing."""
    row = info_row(SystemId=11, Date_Buffer_1=NOW - timedelta(seconds=11),
                   Date_Buffer_2=NOW - timedelta(seconds=13))
    turbine = Turbine(name="TG1", system_id=11, buffers=["buffer_le", "buffer_le_3"])
    connection = FakeConnection(info_rows=[row],
                                table_rows={"buffer_le": 1, "buffer_le_3": 2})

    values = make_collector(connection).collect(turbine, NOW)

    assert values["vms.buf_age"] == 13


def test_the_older_buffer_wins_whichever_position_it_has():
    """The worst buffer decides, no matter which of the two it is."""
    row = info_row(SystemId=11, Date_Buffer_1=NOW - timedelta(seconds=99),
                   Date_Buffer_2=NOW - timedelta(seconds=2))
    turbine = Turbine(name="TG1", system_id=11, buffers=["buffer_le", "buffer_le_3"])
    connection = FakeConnection(info_rows=[row], table_rows={})

    values = make_collector(connection).collect(turbine, NOW)

    assert values["vms.buf_age"] == 99


def test_turbine_without_buffers_reports_zero():
    """UC3-R3: the three buffer metrics are still sent, as zeros."""
    turbine = Turbine(name="TG1", system_id=11, buffers=[])
    connection = FakeConnection(info_rows=[info_row(SystemId=11)])

    values = make_collector(connection).collect(turbine, NOW)

    for key in ("vms.buf_rows", "vms.buf_age", "vms.buf_bulk"):
        assert values[key] == 0


def test_buffer_table_name_does_not_choose_the_info_columns():
    """UC4-R5: age and bulk follow the position of the buffer, not its name."""
    turbine = Turbine(name="TG1", system_id=11, buffers=["buffer_le_3", "buffer_le"])
    connection = FakeConnection(info_rows=[info_row(SystemId=11)],
                                table_rows={"buffer_le": 157062, "buffer_le_3": 58043})

    values = make_collector(connection).collect(turbine, NOW)

    # Swapping the names in the configuration changes neither the columns the age
    # and the bulk come from nor the sums, which cover both tables anyway.
    assert values["vms.buf_age"] == 13
    assert values["vms.buf_bulk"] == 36
    assert values["vms.buf_rows"] == 215105


def test_missing_buffer_table_counts_no_rows():
    """A configured buffer table the database does not have counts 0 rows."""
    turbine = Turbine(name="TG1", system_id=11, buffers=["buffer_gone"])
    connection = FakeConnection(info_rows=[info_row(SystemId=11)], table_rows={})

    values = make_collector(connection).collect(turbine, NOW)

    assert values["vms.buf_rows"] == 0


def test_missing_buffer_table_is_worth_a_warning():
    """UC5-R3: zero rows and a missing table look the same, so it is said out loud."""
    turbine = Turbine(name="TG1", system_id=11, buffers=["buffer_gone"])
    connection = FakeConnection(info_rows=[info_row(SystemId=11)], table_rows={})
    collector = make_collector(connection)

    collector.collect(turbine, NOW)

    assert len(collector.warnings) == 1
    assert "buffer_gone" in collector.warnings[0]
    assert "TG1" in collector.warnings[0]


def test_a_buffer_table_that_is_there_warns_about_nothing():
    turbine = Turbine(name="TG1", system_id=11, buffers=["buffer_le"])
    connection = FakeConnection(info_rows=[info_row(SystemId=11)],
                                table_rows={"buffer_le": 0})
    collector = make_collector(connection)

    collector.collect(turbine, NOW)

    assert collector.warnings == []


def test_warnings_do_not_pile_up_between_turbines():
    """Each collect() says what it found itself, not what the one before found."""
    connection = FakeConnection(info_rows=[info_row(SystemId=11)],
                                table_rows={"buffer_le": 5})
    collector = make_collector(connection)

    collector.collect(Turbine(name="TG1", system_id=11, buffers=["chybi"]), NOW)
    collector.collect(Turbine(name="TG2", system_id=11, buffers=["buffer_le"]), NOW)

    assert collector.warnings == []


def test_info_row_is_read_by_system_id_from_the_configured_table():
    """UC4-R2: the row is chosen by the system_id of the turbine."""
    turbine = Turbine(name="TG2", system_id=12, buffers=[])
    connection = FakeConnection(info_rows=[
        info_row(SystemId=11, Phase_Marker=2000010),
        info_row(SystemId=12, Phase_Marker=10000140),
    ])

    values = make_collector(connection, info_table="info_xx").collect(turbine, NOW)

    query, params = connection.executed[0]
    assert "`info_xx`" in query
    assert "`SystemId` = %s" in query
    assert params == (12,)
    assert values["vms.speed"] == round(1e8 / 10000140 * 60, 4)


def test_info_columns_are_enumerated_by_name():
    """UC4-R3: the query names its columns instead of selecting everything."""
    turbine = Turbine(name="TG1", system_id=11, buffers=[])
    connection = FakeConnection(info_rows=[info_row(SystemId=11)])

    make_collector(connection).collect(turbine, NOW)

    query = connection.executed[0][0]
    assert "*" not in query
    for column in INFO_COLUMNS:
        assert f"`{column}`" in query


def test_buffer_rows_are_read_for_the_configured_database():
    """UC4-R5: row counts come from information_schema for the configured tables."""
    turbine = Turbine(name="TG1", system_id=11, buffers=["buffer_le"])
    connection = FakeConnection(info_rows=[info_row(SystemId=11)],
                                table_rows={"buffer_le": 5})

    make_collector(connection, database="BVMS2").collect(turbine, NOW)

    query, params = connection.executed[1]
    assert "information_schema.TABLES" in query
    assert "TABLE_ROWS" in query
    assert params == ("BVMS2", "buffer_le")


def test_turbine_without_buffers_asks_no_table_query():
    """A turbine with no buffer needs nothing from information_schema."""
    turbine = Turbine(name="TG1", system_id=11, buffers=[])
    connection = FakeConnection(info_rows=[info_row(SystemId=11)])

    make_collector(connection).collect(turbine, NOW)

    assert len(connection.executed) == 1


@pytest.mark.parametrize("prefix, name, created", [
    ("btt_tg11", "btt_tg11_20260925120000", datetime(2026, 9, 25, 12, 0, 0)),
    ("btt_tg2a", "btt_tg2a_20260925081530", datetime(2026, 9, 25, 8, 15, 30)),
    ("tg11_out", "tg11_out_20260925", datetime(2026, 9, 25)),
    ("tvms_tg31", "tvms_tg31_20260925", datetime(2026, 9, 25)),
    # MySQL on Windows keeps the names in lower case and compares them without it.
    ("btt_tg1", "BTT_TG1_20260925120000", datetime(2026, 9, 25, 12, 0, 0)),
])
def test_a_raw_data_table_carries_its_date_in_the_name(prefix, name, created):
    """UC6-R2: VMS names its tables down to the second, TVMS by the day."""
    assert raw_table_created(prefix, name) == created


@pytest.mark.parametrize("prefix, name", [
    # A prefix that merely starts another one.
    ("btt_tg1", "btt_tg11_20260925120000"),
    ("btt_tg2", "btt_tg2a_20260925120000"),
    ("tvms_tg3", "tvms_tg31_20260925"),
    ("tg11", "tg11_out_20260925"),
    # Something that is not the date of a raw data table.
    ("btt_tg1", "btt_tg1"),
    ("btt_tg1", "btt_tg1_2026092512"),
    ("btt_tg1", "btt_tg1_20260925120000_old"),
    ("btt_tg1", "btt_tg1x20260925120000"),
    ("btt_tg1", "btt_tg1_20261340120000"),
    ("tg11_out", "tg11_out_20260231"),
])
def test_a_table_the_name_does_not_fit_is_not_a_raw_data_table(prefix, name):
    """UC6-R2: only the whole name <prefix>_<date> with a valid date belongs."""
    assert raw_table_created(prefix, name) is None


def test_the_like_pattern_takes_underscores_literally():
    """UC6-R2: an underscore left alone would let btt_tg1 match btt_tg11_..."""
    assert like_prefix("tg11_out") == r"tg11\_out\_%"
    assert like_regex(like_prefix("btt_tg1")).fullmatch("btt_tg1_20260925120000")
    assert not like_regex(like_prefix("btt_tg1")).fullmatch("btt_tg11_20260925120000")


def raw_turbine(*prefixes):
    return Turbine(name="TG1", system_id=11, buffers=[], raw_prefixes=list(prefixes))


def collect_raw(turbine, raw_tables, database="BVMS", created=None):
    connection = FakeConnection(info_rows=[info_row(SystemId=11)], raw_tables=raw_tables,
                                raw_created=created)
    collector = make_collector(connection, database=database)
    return collector.collect(turbine, NOW), connection, collector


def test_raw_data_values_follow_the_source_table():
    """UC6-R3, UC6-R4: the tables of the prefix are counted and the newest one's write
    is the age."""
    values, _, _ = collect_raw(raw_turbine("btt_tg1"), {
        vms_table("btt_tg1", NOW - timedelta(hours=1)): NOW - timedelta(seconds=10),
        vms_table("btt_tg1", NOW - timedelta(hours=5)): NOW - timedelta(hours=1),
    })

    assert values["vms.raw_tables"] == 2
    assert values["vms.raw_write_age"] == 10


def test_a_write_into_an_older_table_does_not_count():
    """UC6-R4: only the newest table is written to, an older one waits for its export;
    which one is the newest says its name, not its write."""
    values, _, _ = collect_raw(raw_turbine("btt_tg1"), {
        vms_table("btt_tg1", NOW - timedelta(hours=1)): NOW - timedelta(seconds=600),
        vms_table("btt_tg1", NOW - timedelta(hours=5)): NOW - timedelta(seconds=1),
    })

    assert values["vms.raw_write_age"] == 600


def test_the_count_is_that_of_the_prefix_with_the_most_tables():
    """UC6-R3: tables piling up under one prefix are a failed export, however few the
    other prefixes have."""
    written = NOW - timedelta(seconds=5)
    tables = {vms_table("btt_tg2a", NOW - timedelta(hours=1)): written,
              vms_table("btt_tg2c", NOW - timedelta(hours=1)): written}
    for hours in (1, 5, 9):
        tables[vms_table("btt_tg2b", NOW - timedelta(hours=hours))] = written

    values, _, _ = collect_raw(raw_turbine("btt_tg2a", "btt_tg2b", "btt_tg2c"), tables)

    assert values["vms.raw_tables"] == 3


def test_the_write_age_is_that_of_the_worst_prefix():
    """UC6-R4: one prefix that stopped writing is enough, the others do not hide it."""
    values, _, _ = collect_raw(raw_turbine("btt_tg2a", "btt_tg2b"), {
        vms_table("btt_tg2a", NOW - timedelta(hours=1)): NOW - timedelta(seconds=5),
        vms_table("btt_tg2b", NOW - timedelta(hours=1)): NOW - timedelta(seconds=400),
    })

    assert values["vms.raw_write_age"] == 400


def test_vms_and_tvms_of_one_turbine_are_summed_up_together():
    """UC6-R1, UC6-R3, UC6-R4: a turbine with both systems reports the worse of them."""
    values, _, _ = collect_raw(raw_turbine("btt_tg11", "tg11_out"), {
        vms_table("btt_tg11", NOW - timedelta(hours=1)): NOW - timedelta(seconds=3),
        vms_table("btt_tg11", NOW - timedelta(hours=5)): NOW - timedelta(hours=1),
        tvms_table("tg11_out", NOW): NOW - timedelta(seconds=700),
    })

    assert values["vms.raw_tables"] == 2
    assert values["vms.raw_write_age"] == 700


def test_the_newest_tvms_table_is_the_one_of_the_latest_day():
    """UC6-R2: TVMS tables are told apart by their day."""
    values, _, _ = collect_raw(raw_turbine("tvms_tg31"), {
        tvms_table("tvms_tg31", NOW): NOW - timedelta(seconds=20),
        tvms_table("tvms_tg31", NOW - timedelta(days=1)): NOW - timedelta(seconds=1),
    })

    assert values["vms.raw_write_age"] == 20


def test_a_prefix_without_a_table_is_as_old_as_it_gets():
    """UC6-R3, UC6-R4: no table means nothing is written, but it adds no table."""
    values, _, _ = collect_raw(raw_turbine("btt_tg1", "tg11_out"), {
        vms_table("btt_tg1", NOW - timedelta(hours=1)): NOW - timedelta(seconds=10),
    })

    assert values["vms.raw_tables"] == 1
    assert values["vms.raw_write_age"] == MAX_AGE_SECONDS


def test_a_table_without_an_update_time_is_as_old_as_it_gets():
    """UC6-R4: InnoDB forgets it on a restart of MySQL, until the next write, and the
    table is long past its first minute."""
    table = vms_table("btt_tg1", NOW - timedelta(hours=1))
    values, _, _ = collect_raw(raw_turbine("btt_tg1"), {table: None},
                               created={table: NOW - timedelta(hours=1)})

    assert values["vms.raw_write_age"] == MAX_AGE_SECONDS


def test_a_table_created_a_moment_ago_is_no_stopped_write():
    """UC6-R5: the system creates the new table and writes into it a moment later; a
    cycle in between sees it empty and counts from its creation, not from the write
    into the table before."""
    started = NOW - timedelta(seconds=59)
    new = vms_table("btt_tg1", started)
    values, _, _ = collect_raw(raw_turbine("btt_tg1"), {
        new: None,
        vms_table("btt_tg1", NOW - timedelta(hours=4)): NOW - timedelta(seconds=5),
    }, created={new: started})

    assert values["vms.raw_tables"] == 2
    assert values["vms.raw_write_age"] == 59


def test_a_new_table_still_empty_after_a_minute_is_as_old_as_it_gets():
    """UC6-R4, UC6-R5: once the minute is over, nothing written is a stopped write."""
    started = NOW - timedelta(minutes=1)
    new = vms_table("btt_tg1", started)
    values, _, _ = collect_raw(raw_turbine("btt_tg1"), {new: None},
                               created={new: started})

    assert values["vms.raw_write_age"] == MAX_AGE_SECONDS


def test_a_young_table_written_to_counts_its_write():
    """UC6-R5: the creation stands in only for a write that has not come yet."""
    started = NOW - timedelta(seconds=30)
    new = vms_table("btt_tg1", started)
    values, _, _ = collect_raw(raw_turbine("btt_tg1"), {new: NOW - timedelta(seconds=4)},
                               created={new: started})

    assert values["vms.raw_write_age"] == 4


def test_the_minute_runs_from_the_creation_not_from_the_name():
    """UC6-R5: the day in the name of a TVMS table says nothing of when in that day
    the table came to be."""
    today = tvms_table("tvms_tg31", NOW)
    values, _, _ = collect_raw(raw_turbine("tvms_tg31"), {
        today: None,
        tvms_table("tvms_tg31", NOW - timedelta(days=1)): NOW - timedelta(seconds=30),
    }, created={today: NOW - timedelta(seconds=20)})

    assert values["vms.raw_write_age"] == 20


def test_a_table_created_who_knows_when_gets_no_minute():
    """UC6-R4: without CREATE_TIME nothing says the table is new."""
    values, _, _ = collect_raw(raw_turbine("btt_tg1"), {
        vms_table("btt_tg1", NOW - timedelta(seconds=10)): None,
    })

    assert values["vms.raw_write_age"] == MAX_AGE_SECONDS


def test_a_table_the_pattern_lets_through_but_the_name_does_not_fit_is_left_out():
    """UC6-R2: LIKE only narrows the query, the name decides."""
    values, _, _ = collect_raw(raw_turbine("btt_tg1"), {
        vms_table("btt_tg1", NOW - timedelta(hours=1)): NOW - timedelta(seconds=10),
        "btt_tg1_export": NOW - timedelta(seconds=1),
        "btt_tg1_20261340120000": NOW - timedelta(seconds=1),
        vms_table("btt_tg11", NOW - timedelta(hours=1)): NOW - timedelta(seconds=1),
    })

    assert values["vms.raw_tables"] == 1
    assert values["vms.raw_write_age"] == 10


def test_turbine_without_raw_data_prefixes_reports_zero():
    """UC6-R1: both raw data metrics are still sent, as zeros, and nothing is asked."""
    values, connection, _ = collect_raw(raw_turbine(), {
        vms_table("btt_tg1", NOW - timedelta(hours=1)): NOW,
    })

    assert values["vms.raw_tables"] == 0
    assert values["vms.raw_write_age"] == 0
    assert not [query for query, _ in connection.executed if " LIKE " in query]


def test_raw_data_tables_are_asked_for_in_the_configured_database():
    """UC6-R2: one query over information_schema for all prefixes of the turbine."""
    _, connection, _ = collect_raw(raw_turbine("btt_tg11", "tg11_out"), {},
                                   database="BVMS2")

    query, params = connection.executed[-1]
    assert "information_schema.TABLES" in query
    assert "UPDATE_TIME" in query
    assert "CREATE_TIME" in query
    assert params == ("BVMS2", r"btt\_tg11\_%", r"tg11\_out\_%")


def test_a_missing_raw_data_table_is_no_warning():
    """What a prefix without tables means is what the trigger reports, not the agent."""
    _, _, collector = collect_raw(raw_turbine("btt_tg1"), {})

    assert collector.warnings == []


def test_missing_info_row_is_an_error():
    """UC4-R2: a turbine whose system_id has no row cannot be measured."""
    turbine = Turbine(name="TG9", system_id=99, buffers=[])
    connection = FakeConnection(info_rows=[info_row(SystemId=11)])

    with pytest.raises(CollectorError):
        make_collector(connection).collect(turbine, NOW)


def test_collect_without_connect_is_an_error():
    config = DatabaseConfig()
    collector = Collector(config, connect=lambda **kwargs: FakeConnection())

    with pytest.raises(CollectorError):
        collector.collect(Turbine(), NOW)


def test_connect_uses_the_values_from_the_configuration():
    """UC2-R6: the agent connects to what the configuration says."""
    captured = {}

    def connect(**kwargs):
        captured.update(kwargs)
        return FakeConnection()

    config = DatabaseConfig(host="db.example.com", database="BVMS2", user="reader",
                            password="secret", info_table="info_xx")
    Collector(config, connect=connect).connect()

    assert captured == {"host": "db.example.com", "database": "BVMS2",
                        "user": "reader", "password": "secret", "use_pure": True,
                        "autocommit": True}


def test_connect_stays_away_from_the_c_extension():
    """UC2-R6: libmysql.dll needs a Visual C++ runtime the servers may not have."""
    captured = {}

    def connect(**kwargs):
        captured.update(kwargs)
        return FakeConnection()

    Collector(DatabaseConfig(), connect=connect).connect()

    assert captured["use_pure"] is True


def test_no_transaction_is_left_open_between_queries():
    """UC4-R8: an open transaction would answer every query from the snapshot of its
    first one, information_schema of MySQL 8 included, so a raw data table created
    while the agent runs would never be seen."""
    captured = {}

    def connect(**kwargs):
        captured.update(kwargs)
        return FakeConnection()

    Collector(DatabaseConfig(), connect=connect).connect()

    assert captured["autocommit"] is True


def test_close_releases_the_connection():
    connection = FakeConnection()
    collector = make_collector(connection)

    collector.close()
    collector.close()

    assert connection.closed


STATS_EXPIRY_OFF = "SET SESSION information_schema_stats_expiry = 0"


def test_the_session_reads_the_statistics_from_the_engine():
    """UC4-R7: MySQL 8 would answer TABLE_ROWS and UPDATE_TIME from a cache refreshed
    once a day; the session of the agent asks the engine instead."""
    connection = FakeConnection()

    make_collector(connection)

    assert connection.settings == [STATS_EXPIRY_OFF]


def test_the_setting_is_made_again_on_every_new_connection():
    """UC4-R7: after a failed cycle the connection is opened afresh, and a session
    setting does not outlive the session it was made in."""
    connections = [FakeConnection(), FakeConnection()]
    collector = Collector(DatabaseConfig(), connect=lambda **kwargs: connections.pop(0))
    first, second = connections

    collector.connect()
    collector.close()
    collector.connect()

    assert first.settings == second.settings == [STATS_EXPIRY_OFF]


def test_a_server_without_the_statistics_cache_is_fine():
    """UC4-R7: MySQL 5.7 does not know the variable, and has no cache to turn off."""
    unknown = mysql.connector.errors.DatabaseError(
        msg="Unknown system variable 'information_schema_stats_expiry'",
        errno=errorcode.ER_UNKNOWN_SYSTEM_VARIABLE)
    turbine = Turbine(name="TG1", system_id=11, buffers=[])
    connection = FakeConnection(info_rows=[info_row(SystemId=11)], refuse_settings=unknown)

    values = make_collector(connection).collect(turbine, NOW)

    assert values["vms.info_age"] == 3


def test_another_failure_of_the_setting_is_not_swallowed():
    """Only the unknown variable means there is no cache; anything else is a fault."""
    denied = mysql.connector.errors.ProgrammingError(
        msg="Access denied", errno=errorcode.ER_SPECIFIC_ACCESS_DENIED_ERROR)
    connection = FakeConnection(refuse_settings=denied)

    with pytest.raises(mysql.connector.Error):
        make_collector(connection)
