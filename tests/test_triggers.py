"""Tests of the trigger catalog: it holds exactly the triggers of the table in the
PRS and every one of them watches a metric of the catalog (UC5-R4)."""

from pathlib import Path

from zabbixvms import metrics
from zabbixvms.metrics import METRIC_PLACEHOLDER, TRIGGERS
from zabbixvms.template import TEMPLATE_NAME, expression_of

PRS = Path(__file__).resolve().parent.parent / "doc" / "PRS-zabbixvms.md"
HEADER = "| Název triggeru | Klíč metriky | Podmínka | Priorita |"

ZABBIX_PRIORITIES = {"NOT_CLASSIFIED", "INFO", "WARNING", "AVERAGE", "HIGH", "DISASTER"}


def prs_trigger_rows():
    """Rows of the trigger table in the PRS, each as a list of its cells."""
    lines = PRS.read_text(encoding="utf-8").splitlines()
    start = lines.index(HEADER)
    rows = []
    for line in lines[start + 2:]:
        if not line.startswith("|"):
            break
        rows.append([cell.strip() for cell in line.strip().strip("|").split("|")])
    return rows


def test_prs_table_is_readable():
    """The test below is only meaningful while the table is found and parsed."""
    rows = prs_trigger_rows()

    assert len(rows) > 1
    assert all(len(row) == 4 for row in rows)


def test_catalog_matches_the_prs_table():
    """UC5-R4: the template carries the triggers of the table, no more and no fewer."""
    catalog = [[trigger.name, f"`{trigger.key}`", f"`{trigger.condition}`",
                trigger.priority]
               for trigger in TRIGGERS]

    assert catalog == prs_trigger_rows()


def test_every_trigger_watches_a_metric_of_the_catalog():
    """UC5-R4: a trigger on a key that is not sent would never fire."""
    for trigger in TRIGGERS:
        assert trigger.key in metrics.KEYS


def test_every_condition_refers_to_its_metric():
    """The condition has to name the metric, otherwise the key means nothing."""
    for trigger in TRIGGERS:
        assert METRIC_PLACEHOLDER in trigger.condition


def test_priorities_are_ones_zabbix_knows():
    for trigger in TRIGGERS:
        assert trigger.priority in ZABBIX_PRIORITIES


def test_names_are_unique():
    assert len({trigger.name for trigger in TRIGGERS}) == len(TRIGGERS)


def test_the_placeholder_becomes_the_reference_to_the_metric():
    """UC5-R4: {METRIC} stands for /<šablona>/<klíč>."""
    trigger = TRIGGERS[0]

    expression = expression_of(trigger)

    assert METRIC_PLACEHOLDER not in expression
    assert f"/{TEMPLATE_NAME}/{trigger.key}" in expression


def test_the_table_holds_the_three_triggers_the_dod_names():
    """UC5-R4: state of the agent, its error text, and a host that says nothing."""
    by_key = {}
    for trigger in TRIGGERS:
        by_key.setdefault(trigger.key, []).append(trigger)

    conditions = [t.condition for t in by_key["vms.agent_status"]]
    assert any(condition.startswith("last(") for condition in conditions)
    assert any(condition.startswith("nodata(") for condition in conditions)
    assert "{ITEM.VALUE}" in by_key["vms.agent_error"][0].name
