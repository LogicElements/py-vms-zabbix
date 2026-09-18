"""Tests of the trigger catalog: it holds exactly the triggers of the table in the
PRS and every one of them watches a metric of the catalog (UC5-R4)."""

import re
from pathlib import Path

from zabbixvms import metrics
from zabbixvms.metrics import METRIC_PLACEHOLDER, TRIGGERS
from zabbixvms.template import TEMPLATE_NAME, expression_of

PRS = Path(__file__).resolve().parent.parent / "doc" / "PRS-zabbixvms.md"
HEADER = "| Název triggeru | Klíč metriky | Podmínka | Priorita | Závisí na |"
# What the dependency cell holds for a trigger that nothing blocks.
NOTHING = "–"

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
    assert all(len(row) == 5 for row in rows)


def test_catalog_matches_the_prs_table():
    """UC5-R4: the template carries the triggers of the table, no more and no fewer."""
    catalog = [[trigger.name, f"`{trigger.key}`", f"`{trigger.condition}`",
                trigger.priority, trigger.blocked_by or NOTHING]
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


def test_triggers_on_a_value_show_it_in_their_name():
    """The list of problems shows the name, so the value belongs in it.

    A trigger that fires on the value of its metric says what that value was;
    nodata() fires on the absence of one, so there is nothing to show.
    """
    for trigger in TRIGGERS:
        if trigger.condition.startswith("nodata("):
            assert "{ITEM.VALUE}" not in trigger.name
        elif trigger.key.startswith("vms.buf") or trigger.key.endswith("_age") \
                or trigger.key == "vms.agent_error":
            assert "{ITEM.VALUE}" in trigger.name, trigger.name


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


def test_every_dependency_names_a_trigger_of_the_catalog():
    """UC5-R4: a dependency on a name nothing carries would be dropped on import."""
    for trigger in TRIGGERS:
        if trigger.blocked_by:
            assert metrics.trigger_named(trigger.blocked_by)


def test_only_what_a_standing_turbine_stops_writing_waits_for_it():
    """UC5-R4: the setup database is written whether the turbine turns or not, so the
    trigger on its age keeps firing; the measurements it stops writing do not."""
    blocked = {trigger.key for trigger in TRIGGERS if trigger.blocked_by}

    assert blocked == {"vms.timestamp_age", "vms.config_age", "vms.buf_age"}
    assert all(trigger.blocked_by == metrics.TURBINE_BELOW_NOMINAL
               for trigger in TRIGGERS if trigger.blocked_by)


def test_nothing_blocks_the_trigger_that_blocks_the_others():
    """A trigger that depends on itself, however indirectly, never fires."""
    for trigger in TRIGGERS:
        seen = {trigger.name}
        blocker = trigger.blocked_by
        while blocker:
            assert blocker not in seen, trigger.name
            seen.add(blocker)
            blocker = metrics.trigger_named(blocker).blocked_by


def test_every_macro_a_condition_uses_is_declared():
    """UC5-R4: an undeclared macro leaves the condition without a threshold."""
    declared = {macro.name for macro in metrics.MACROS}
    found = []
    for trigger in TRIGGERS:
        for used in re.findall(r"\{\$[^}]+\}", trigger.condition):
            found.append(used)
            assert used in declared, f"{trigger.name}: {used}"
    # Without a condition that really uses one, the loop above proves nothing.
    assert found
