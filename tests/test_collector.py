"""Tests of the collector against faked database objects: the computations of the
source table, the -1 limit and the zeros of an unconfigured buffer
(UC4-R1, UC4-R2, UC4-R3, UC4-R4, UC4-R5, UC3-R3)."""

from datetime import datetime, timedelta

import pytest

from zabbixvms import metrics
from zabbixvms.collector import (
    INFO_COLUMNS,
    MAX_AGE,
    MAX_AGE_SECONDS,
    MIN_SPEED,
    Collector,
    CollectorError,
    age,
    speed,
)
from zabbixvms.config import DatabaseConfig, Turbine

NOW = datetime(2026, 9, 14, 12, 0, 0)


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
    """Cursor that answers the two queries of the collector from prepared rows."""

    def __init__(self, fake):
        self._fake = fake
        self._rows = []

    def execute(self, query, params=None):
        self._fake.executed.append((query, params))
        if "information_schema" in query:
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
    def __init__(self, info_rows=(), table_rows=None):
        self.info_rows = list(info_rows)
        self.table_rows = dict(table_rows or {})
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
                        "user": "reader", "password": "secret", "use_pure": True}


def test_connect_stays_away_from_the_c_extension():
    """UC2-R6: libmysql.dll needs a Visual C++ runtime the servers may not have."""
    captured = {}

    def connect(**kwargs):
        captured.update(kwargs)
        return FakeConnection()

    Collector(DatabaseConfig(), connect=connect).connect()

    assert captured["use_pure"] is True


def test_close_releases_the_connection():
    connection = FakeConnection()
    collector = make_collector(connection)

    collector.close()
    collector.close()

    assert connection.closed
