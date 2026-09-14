"""Tests of the collector against the BVMS test database. They are skipped when
no such database is reachable (UC4-R2, UC4-R3, UC4-R5)."""

from datetime import datetime

import mysql.connector
import pytest

from zabbixvms import collector as collector_module
from zabbixvms.collector import INFO_COLUMNS, Collector
from zabbixvms.config import DatabaseConfig, Turbine

pytestmark = pytest.mark.db

NOW = datetime(2026, 9, 14, 12, 0, 0)


@pytest.fixture(scope="module")
def database():
    return DatabaseConfig()


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


def test_collect_fills_the_catalog_from_the_database(collector, system_ids):
    """The whole read plus computation works against the real schema."""
    from zabbixvms import metrics

    turbine = Turbine(name="TG", system_id=system_ids[0], buffers=["buffer_le"])

    values = collector.collect(turbine, NOW)

    assert set(values) == set(metrics.COLLECTOR_KEYS)
    assert all(isinstance(value, (int, float)) for value in values.values())
