"""Tests of the collector against the BVMS test database. They are skipped when
no such database is reachable (UC4-R2, UC4-R3, UC4-R5, UC4-R8, UC6-R2, UC8-R3, UC8-R4)."""

import os
import time
import uuid
from datetime import datetime, timedelta

import mysql.connector
import pytest

from zabbixvms import collector as collector_module
from zabbixvms.collector import INFO_COLUMNS, Collector, CollectorError, trend_age, trend_queries
from zabbixvms.config import DatabaseConfig, Turbine

pytestmark = pytest.mark.db

NOW = datetime(2026, 9, 14, 12, 0, 0)


@pytest.fixture(scope="module")
def database():
    """Connection to the test database. The package carries no password, so the tests
    take it, and where the database is, from the environment."""
    password = os.environ.get("ZABBIXVMS_TEST_DB_PASSWORD")
    if password is None:
        pytest.skip("set ZABBIXVMS_TEST_DB_PASSWORD to the password of the BVMS test "
                    "database, ZABBIXVMS_TEST_DB_HOST, _USER and _NAME when they differ "
                    "from localhost, VMS and BVMS")
    return DatabaseConfig(
        host=os.environ.get("ZABBIXVMS_TEST_DB_HOST", "localhost"),
        user=os.environ.get("ZABBIXVMS_TEST_DB_USER", "VMS"),
        database=os.environ.get("ZABBIXVMS_TEST_DB_NAME", "BVMS"),
        password=password,
    )


@pytest.fixture(scope="module")
def collector(database):
    instance = Collector(database)
    try:
        instance.connect()
    except mysql.connector.Error as err:
        pytest.skip(f"BVMS test database is not reachable: {err}")
    yield instance
    instance.close()


@pytest.fixture(scope="module")
def raw(database, collector):
    """Direct connection used to check the collector against the database."""
    connection = mysql.connector.connect(
        host=database.host, database=database.database,
        user=database.user, password=database.password,
    )
    yield connection
    connection.close()


def query(connection, sql, params=()):
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(sql, params)
        return cursor.fetchall()
    finally:
        cursor.close()


@pytest.fixture(scope="module")
def system_ids(raw, database):
    rows = query(raw, f"SELECT `SystemId` FROM `{database.info_table}` "
                      f"ORDER BY `SystemId`")
    ids = [row["SystemId"] for row in rows]
    if len(ids) < 2:
        pytest.skip("the info table needs at least two systems for these tests")
    return ids


def test_info_row_is_read_for_the_given_system(collector, raw, database, system_ids):
    """UC4-R2: the row read for a turbine is the row of its system_id."""
    system_id = system_ids[0]
    expected = query(raw, f"SELECT `Phase_Marker`, `Date` FROM `{database.info_table}` "
                          f"WHERE `SystemId` = %s", (system_id,))[0]

    row = collector.read_info(Turbine(name="TG", system_id=system_id))

    assert row["Phase_Marker"] == expected["Phase_Marker"]
    assert row["Date"] == expected["Date"]
    assert set(row) == set(INFO_COLUMNS)


def test_another_system_gives_another_row(collector, system_ids):
    """UC4-R2: values of one turbine are not taken from another turbine's row."""
    first = collector.read_info(Turbine(name="TG1", system_id=system_ids[0]))
    second = collector.read_info(Turbine(name="TG2", system_id=system_ids[-1]))

    assert first != second


def test_values_do_not_depend_on_the_column_order(collector, monkeypatch, system_ids):
    """UC4-R3: reordering the selected columns changes no value."""
    turbine = Turbine(name="TG", system_id=system_ids[0])
    expected = collector.read_info(turbine)

    monkeypatch.setattr(collector_module, "INFO_COLUMNS", tuple(reversed(INFO_COLUMNS)))
    reordered = collector.read_info(turbine)

    assert reordered == expected


def test_buffer_row_counts_are_read_by_table_name(collector, raw, database):
    """UC4-R5: row counts come from information_schema for the named tables."""
    tables = [row["TABLE_NAME"] for row in query(
        raw, "SELECT TABLE_NAME FROM information_schema.TABLES "
             "WHERE TABLE_SCHEMA = %s AND TABLE_NAME LIKE 'buffer%%' "
             "ORDER BY TABLE_NAME", (database.database,))]
    if len(tables) < 2:
        pytest.skip("the test database needs at least two buffer tables")
    buffers = tables[:2]

    counts = collector.read_buffer_rows(Turbine(name="TG", system_id=1, buffers=buffers))

    assert set(counts) == set(buffers)
    assert all(isinstance(count, int) and count >= 0 for count in counts.values())


def test_unknown_buffer_table_is_not_counted(collector):
    """A table the database does not have contributes no row count."""
    turbine = Turbine(name="TG", system_id=1, buffers=["buffer_that_is_not_there"])

    assert collector.read_buffer_rows(turbine) == {}


def test_raw_data_prefix_without_tables_is_asked_for_and_empty(collector):
    """UC6-R2: the query with its escaped LIKE runs against the real information_schema,
    and a prefix nothing in the database carries has no table."""
    turbine = Turbine(name="TG", system_id=1, raw_prefixes=["btt_that_is_not_there",
                                                            "tvms_that_is_not_there"])

    assert collector.read_raw_tables(turbine) == {"btt_that_is_not_there": [],
                                                  "tvms_that_is_not_there": []}


def test_tables_that_only_start_like_a_prefix_are_not_raw_data(collector, raw, database):
    """UC6-R2: buffer_le_2 and buffer_le_3 start with buffer_le_, which LIKE lets
    through, but without a date they are no raw data tables of it."""
    started = query(raw, "SELECT TABLE_NAME FROM information_schema.TABLES "
                         "WHERE TABLE_SCHEMA = %s AND TABLE_NAME LIKE 'buffer\\_le\\_%%'",
                    (database.database,))
    if not started:
        pytest.skip("the test database needs a table named buffer_le_<something>")

    turbine = Turbine(name="TG", system_id=1, raw_prefixes=["buffer_le"])

    assert collector.read_raw_tables(turbine) == {"buffer_le": []}


def test_the_connection_of_the_agent_commits_every_query(collector):
    """UC4-R8: no transaction stays open, so no snapshot outlives its query."""
    assert collector._connection.autocommit is True


def test_collect_fills_the_catalog_from_the_database(collector, system_ids):
    """The whole read plus computation works against the real schema."""
    from zabbixvms import metrics

    turbine = Turbine(name="TG", system_id=system_ids[0], buffers=["buffer_le"])

    values = collector.collect(turbine, NOW)

    # The turbine watches no trend signal, so it has no age of them.
    assert set(values) == set(metrics.COLLECTOR_KEYS) - {"vms.trend_age"}
    assert all(isinstance(value, (int, float)) for value in values.values())


# --- trend data (UC8) ---------------------------------------------------------------
#
# The tests work on a table of their own, made like the trend data table of the servers:
# Id is the primary key and PTimeStamp a DATETIME. The local copy dukovany_local is
# checked by hand, see the plan, its content is too big and too old for a test.

TREND_SIGNALS = [-4058, -4060, -4071, -4072, -4075, -4083]
TREND_TABLE_DDL = (
    "CREATE TABLE `{name}` ("
    "`SigID` int(11) DEFAULT NULL, `PValue` double DEFAULT NULL, "
    "`PStatus` int(11) DEFAULT NULL, `PTimeStamp` datetime DEFAULT NULL, `PMilliSec` char(3) DEFAULT NULL, "
    "`Id` int(11) NOT NULL AUTO_INCREMENT, PRIMARY KEY (`Id`)) ENGINE=InnoDB DEFAULT CHARSET=utf8"
)


def stamp(moment):
    return f"{moment:%Y-%m-%d %H:%M:%S}"


@pytest.fixture()
def trend_table(raw):
    """Name of an empty table of the shape of the trend data table, dropped afterwards."""
    name = f"zabbixvms_trend_test_{uuid.uuid4().hex[:8]}"
    raw.autocommit = True
    cursor = raw.cursor()
    cursor.execute(TREND_TABLE_DDL.format(name=name))
    cursor.close()
    yield name
    cursor = raw.cursor()
    cursor.execute(f"DROP TABLE IF EXISTS `{name}`")
    cursor.close()


def fill(raw, table, rows):
    """Write rows of (SigID, PTimeStamp) into the table, one after another."""
    cursor = raw.cursor()
    cursor.executemany(
        f"INSERT INTO `{table}` (`SigID`, `PValue`, `PStatus`, `PTimeStamp`, `PMilliSec`) "
        f"VALUES (%s, 1.5, 0, %s, '000')", rows)
    cursor.close()


def trend_collector(database, table, window=10000):
    config = DatabaseConfig(host=database.host, database=database.database,
                            user=database.user, password=database.password,
                            trend_table=table, trend_window=window,
                            trend_utc_offset=None)
    instance = Collector(config)
    instance.connect()
    return instance


def explain(raw, sql, params):
    cursor = raw.cursor(dictionary=True)
    try:
        cursor.execute("EXPLAIN " + sql, params)
        return cursor.fetchall()
    finally:
        cursor.close()


def test_trend_signals_are_read_from_the_end_of_the_table(raw, database, trend_table):
    """UC8-R3, UC8-R4: the newest record of each signal is found in the window, and a
    signal that has no record in it is as old as the beginning of the window."""
    rows = [(-4083, stamp(NOW - timedelta(seconds=9000)))]
    rows += [(-4058, stamp(NOW - timedelta(seconds=600 - n))) for n in range(100)]
    rows += [(-4060, stamp(NOW - timedelta(seconds=3)))]
    fill(raw, trend_table, rows)
    reader = trend_collector(database, trend_table, window=1000)
    try:
        window = reader.read_trend(Turbine(name="TG", trend_signals=[-4058, -4060, -4083]))
    finally:
        reader.close()

    assert window.last[-4058] == NOW - timedelta(seconds=501)
    assert window.last[-4060] == NOW - timedelta(seconds=3)
    # 1000 rows reach back over all 102, so the signal that is the oldest is in it.
    assert window.last[-4083] == NOW - timedelta(seconds=9000)
    assert window.oldest == NOW - timedelta(seconds=9000)


def test_a_signal_behind_the_window_is_not_looked_for(raw, database, trend_table):
    """UC8-R3: the table is read by its end only, so what lies behind the window is
    never found and the signal is given the age of the window's beginning."""
    rows = [(-4083, stamp(NOW - timedelta(seconds=9000)))]
    rows += [(-4058, stamp(NOW - timedelta(seconds=1500 - n))) for n in range(2000)]
    fill(raw, trend_table, rows)
    reader = trend_collector(database, trend_table, window=1000)
    try:
        window = reader.read_trend(Turbine(name="TG", trend_signals=[-4058, -4083]))
    finally:
        reader.close()

    assert -4083 not in window.last
    # 2001 rows, the window the last 1000 of them: it starts with the 1001st row of -4058.
    assert window.oldest == NOW - timedelta(seconds=1500 - 1000)
    assert trend_age([-4083], window, NOW) == 1500 - 1000


def test_an_empty_trend_table_gives_an_empty_window(raw, database, trend_table):
    """UC8-R3: no row is no window, which is as old as an age gets."""
    reader = trend_collector(database, trend_table)
    try:
        window = reader.read_trend(Turbine(name="TG", trend_signals=TREND_SIGNALS))
    finally:
        reader.close()

    assert window.last == {} and window.oldest is None


def test_a_trend_table_that_is_not_there_is_an_error(database):
    """UC8-R4: the missing table is told apart from other errors of the database."""
    reader = trend_collector(database, "zabbixvms_trend_that_is_not_there")
    try:
        with pytest.raises(CollectorError, match="zabbixvms_trend_that_is_not_there"):
            reader.read_trend(Turbine(name="TG", trend_signals=TREND_SIGNALS))
    finally:
        reader.close()


def test_trend_queries_walk_a_range_of_the_primary_key_only(raw, trend_table):
    """UC8-R4: the plan of both queries is a range of PRIMARY, never the whole table."""
    fill(raw, trend_table, [(-4058, stamp(NOW)) for _ in range(3000)])
    last_query, oldest_query = trend_queries(trend_table, len(TREND_SIGNALS))

    for sql, params in [(last_query, (500, *TREND_SIGNALS)), (oldest_query, (500,))]:
        main = [row for row in explain(raw, sql, params) if row["select_type"] == "PRIMARY"]
        assert [row["table"] for row in main] == [trend_table]
        assert main[0]["type"] == "range", main[0]
        assert main[0]["key"] == "PRIMARY", main[0]


@pytest.mark.slow
@pytest.mark.skipif(not os.environ.get("ZABBIXVMS_SLOW_TESTS"),
                    reason="builds a table of five million rows, set ZABBIXVMS_SLOW_TESTS=1")
def test_the_trend_age_of_a_table_of_millions_of_rows_is_read_at_once(raw, database,
                                                                     trend_table):
    """UC8-R4: five million rows, one signal not among the newest ones, and the read
    takes no more than 100 ms over a plan that walks a range of the primary key."""
    # MySQL cannot join a temporary table with itself, so the seed is a table of its own.
    seed = f"{trend_table}_seed"
    cursor = raw.cursor()
    cursor.execute(f"CREATE TABLE `{seed}` (`n` int)")
    try:
        cursor.executemany(f"INSERT INTO `{seed}` VALUES (%s)", [(n,) for n in range(200)])
        cursor.execute(
            f"INSERT INTO `{trend_table}` "
            f"(`SigID`, `PValue`, `PStatus`, `PTimeStamp`, `PMilliSec`) "
            f"SELECT -4000 - (a.n MOD 50), 1.5, 0, '2026-01-01 00:00:00', '000' "
            f"FROM `{seed}` a, `{seed}` b, `{seed}` c LIMIT 5000000")
    finally:
        cursor.execute(f"DROP TABLE `{seed}`")
        cursor.close()
    # The newest rows are the first five signals; -4083 stopped long ago.
    fill(raw, trend_table, [(signal, stamp(NOW)) for signal in TREND_SIGNALS[:-1]] * 100)
    reader = trend_collector(database, trend_table)
    turbine = Turbine(name="TG", trend_signals=TREND_SIGNALS)
    try:
        started = time.perf_counter()
        window = reader.read_trend(turbine)
        elapsed = time.perf_counter() - started
    finally:
        reader.close()

    assert elapsed < 0.1, f"the read took {elapsed * 1000:.0f} ms"
    # The signal that stopped has no row in the window, so it is as old as the window's
    # beginning, and that is what decides over the five that are alive.
    assert trend_age(TREND_SIGNALS, window, NOW) == int((NOW - window.oldest).total_seconds())
    assert -4083 not in window.last
    assert window.last[-4058] == NOW
