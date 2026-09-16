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


def test_catalog_splits_into_collector_and_agent_keys():
    """The agent reports its own state, the collector everything else."""
    assert set(metrics.COLLECTOR_KEYS) | set(metrics.AGENT_KEYS) == set(metrics.KEYS)
    assert not set(metrics.COLLECTOR_KEYS) & set(metrics.AGENT_KEYS)


def test_by_key_finds_a_metric():
    assert metrics.by_key("vms.speed").units == "rpm"
