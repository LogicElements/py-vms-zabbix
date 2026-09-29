"""Tests of the metric catalog: it holds exactly the metrics of the table in the
PRS and carries what a Zabbix item needs (UC3-R1, UC3-R2, UC3-R3)."""

import re
from pathlib import Path

from zabbixvms import metrics
from zabbixvms.metrics import METRICS, ValueType

PRS = Path(__file__).resolve().parent.parent / "doc" / "PRS-zabbixvms.md"
HEADER = "| Klíč | Název | Typ hodnoty | Jednotka | Popis |"


def prs_metric_rows():
    """Rows of the metric table in the PRS, each as a list of its cells."""
    lines = PRS.read_text(encoding="utf-8").splitlines()
    start = lines.index(HEADER)
    rows = []
    # Skip the header and the separator row, stop at the end of the table.
    for line in lines[start + 2:]:
        if not line.startswith("|"):
            break
        rows.append([cell.strip() for cell in line.strip().strip("|").split("|")])
    return rows


def test_prs_table_is_readable():
    """The test below is only meaningful while the table is found and parsed."""
    rows = prs_metric_rows()

    assert len(rows) > 1
    assert all(len(row) == 5 for row in rows)


def test_catalog_matches_the_prs_table():
    """UC3-R1: the agent sends the metrics of the table, no more and no fewer."""
    rows = prs_metric_rows()

    catalog = [
        [f"`{metric.key}`", metric.name, metric.value_type.value,
         metric.units, metric.description]
        for metric in METRICS
    ]

    assert catalog == rows


def test_value_types_are_named_the_zabbix_way():
    """UC3-R2: the value type column uses the type names of Zabbix."""
    assert {value_type.value for value_type in ValueType} == {
        "Numeric (float)", "Numeric (unsigned)", "Character"
    }
    assert all(isinstance(metric.value_type, ValueType) for metric in METRICS)


def test_every_metric_has_what_an_item_needs():
    """UC3-R2: an item can be created from a single row, nothing is left blank."""
    for metric in METRICS:
        assert re.fullmatch(r"vms\.[a-z0-9_]+", metric.key)
        assert metric.name
        assert metric.description


def test_keys_are_unique():
    """UC3-R1: no key is in the catalog twice."""
    assert len(set(metrics.KEYS)) == len(metrics.KEYS)


def test_the_buffers_have_one_metric_each_kind():
    """UC3-R3: the buffers are summed into one metric each, without a suffix."""
    for name in ("rows", "age", "bulk"):
        assert f"vms.buf_{name}" in metrics.KEYS

    assert not [key for key in metrics.KEYS
                if key.endswith(("_1", "_2"))]


def test_the_collector_fills_every_metric_of_a_turbine():
    """UC3-R1, UC5-R3: the state of the agent is not a metric of a turbine, so the
    collector has all of them."""
    assert set(metrics.COLLECTOR_KEYS) == set(metrics.KEYS)
    assert not set(metrics.AGENT_KEYS) & set(metrics.KEYS)


def test_by_key_finds_a_metric():
    assert metrics.by_key("vms.speed").units == "rpm"


def table_after(heading, header):
    """Rows of the first table with that header below the heading, as lists of cells."""
    lines = PRS.read_text(encoding="utf-8").splitlines()
    start = lines.index(header, lines.index(heading))
    rows = []
    for line in lines[start + 2:]:
        if not line.startswith("|"):
            break
        rows.append([cell.strip() for cell in line.strip().strip("|").split("|")])
    return rows


UC7 = "## UC7 – Sledování napájení serveru z UPS"


def test_the_server_table_is_readable():
    rows = table_after(UC7, HEADER)

    assert len(rows) > 1
    assert all(len(row) == 5 for row in rows)


def test_server_catalog_matches_its_prs_table():
    """UC3-R1, UC7-R2: the host of the server gets the metrics of the table in UC7,
    no more and no fewer."""
    catalog = [
        [f"`{metric.key}`", metric.name, metric.value_type.value,
         metric.units, metric.description]
        for metric in metrics.SERVER_METRICS
    ]

    assert catalog == table_after(UC7, HEADER)


def test_the_turbine_table_is_the_one_before_uc7():
    """UC3-R1: the table of UC3 keeps describing the hosts of the turbines."""
    assert prs_metric_rows() != table_after(UC7, HEADER)
    assert "`ups.charge`" not in [row[0] for row in prs_metric_rows()]


def test_every_server_metric_has_what_an_item_needs():
    """UC3-R2: an item can be created from a single row, nothing is left blank."""
    for metric in metrics.SERVER_METRICS:
        assert re.fullmatch(r"(vms|ups)\.[a-z0-9_]+", metric.key)
        assert metric.name
        assert metric.description
    assert len(set(metrics.SERVER_KEYS)) == len(metrics.SERVER_KEYS)


def test_the_server_reports_the_state_of_the_agent():
    """UC5-R3: the state of the agent is a metric of the host of the server."""
    assert set(metrics.AGENT_KEYS) <= set(metrics.SERVER_KEYS)
    assert metrics.by_key("ups.charge", metrics.SERVER_METRICS).units == "%"
