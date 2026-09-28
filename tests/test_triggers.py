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
        elif trigger.key.startswith(("vms.buf", "vms.raw")) \
                or trigger.key.endswith("_age") or trigger.key == "vms.agent_error":
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
    """UC5-R4, UC6-R4: a standing turbine stops filling the buffer and the raw data
    tables, so the triggers on the age of those writes wait for it; the other sources
    are written whatever the turbine does."""
    blocked = {trigger.key for trigger in TRIGGERS if trigger.blocked_by}

    assert blocked == {"vms.buf_age", "vms.raw_write_age"}
    assert all(trigger.blocked_by == metrics.TURBINE_BELOW_NOMINAL
               for trigger in TRIGGERS if trigger.blocked_by)


def test_three_raw_data_tables_of_one_prefix_are_a_failed_export():
    """UC6-R3: one table is written, a second waits for its export; three is too many."""
    trigger = next(trigger for trigger in TRIGGERS if trigger.key == "vms.raw_tables")

    assert trigger.condition == "last({METRIC})>2"
    assert not trigger.blocked_by


def test_the_raw_data_write_waits_for_a_standing_turbine():
    """UC6-R4: five minutes without a write, unless the turbine stands."""
    trigger = next(trigger for trigger in TRIGGERS if trigger.key == "vms.raw_write_age")

    assert trigger.condition == "last({METRIC})>5m"
    assert trigger.blocked_by == metrics.TURBINE_BELOW_NOMINAL


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


def test_the_state_trigger_stays_under_the_mail_threshold():
    """Mail goes out from AVERAGE up, and the trigger on vms.agent_error fires together
    with this one and carries the text, so both above the threshold would mail twice."""
    state = next(trigger for trigger in TRIGGERS
                 if trigger.key == "vms.agent_status"
                 and trigger.condition.startswith("last("))
    text = next(trigger for trigger in TRIGGERS if trigger.key == "vms.agent_error")

    assert state.priority == "WARNING"
    assert text.priority == "AVERAGE"


UC7 = "## UC7 – Sledování napájení serveru z UPS"
SERVER_HEADER = "| Název triggeru | Klíč metriky | Podmínka | Priorita |"
MACRO_HEADER = "| Makro | Výchozí hodnota | Význam |"


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


def test_server_triggers_match_their_prs_table():
    """UC7-R5: the template of the server carries the triggers of UC7, no more and no
    fewer; none of them waits for another."""
    catalog = [[trigger.name, f"`{trigger.key}`", f"`{trigger.condition}`",
                trigger.priority] for trigger in metrics.SERVER_TRIGGERS]

    assert catalog == table_after(UC7, SERVER_HEADER)
    assert not any(trigger.blocked_by for trigger in metrics.SERVER_TRIGGERS)


def test_server_macros_match_their_prs_table():
    """UC7-R5: the macros of the server template, with their defaults."""
    catalog = [[f"`{macro.name}`", macro.value, macro.description.rstrip(".")]
               for macro in metrics.SERVER_MACROS]

    assert catalog == table_after(UC7, MACRO_HEADER)


def test_every_server_trigger_watches_a_metric_of_the_server():
    """UC7-R5: a trigger on a key the server host is not sent would never fire."""
    for trigger in metrics.SERVER_TRIGGERS:
        assert trigger.key in metrics.SERVER_KEYS
        assert METRIC_PLACEHOLDER in trigger.condition
        assert trigger.priority in ZABBIX_PRIORITIES


def test_every_macro_a_server_condition_uses_is_declared():
    declared = {macro.name for macro in metrics.SERVER_MACROS}
    found = [used for trigger in metrics.SERVER_TRIGGERS
             for used in re.findall(r"\{\$[^}]+\}", trigger.condition)]

    assert found
    assert set(found) <= declared


def test_the_power_fails_below_the_macro_and_not_at_it():
    """UC7-R6: a charge less than the limit is a problem, the limit itself is not."""
    trigger = next(trigger for trigger in metrics.SERVER_TRIGGERS
                   if trigger.key == "ups.charge")
    macro = next(macro for macro in metrics.SERVER_MACROS
                 if macro.name == "{$VMS.UPS.CHARGE.MIN}")

    assert trigger.condition == "last({METRIC})<{$VMS.UPS.CHARGE.MIN}"
    assert macro.value == "50"
    assert trigger.name == "Chyba napájení: {ITEM.VALUE}"
    assert trigger.priority == "HIGH"


def test_the_server_is_watched_for_silence_like_a_turbine():
    """UC7-R4: the triggers on the state of the agent are the same on both hosts."""
    agent_triggers = [trigger for trigger in TRIGGERS
                      if trigger.key in metrics.AGENT_KEYS]
    server_agent_triggers = [trigger for trigger in metrics.SERVER_TRIGGERS
                             if trigger.key in metrics.AGENT_KEYS]

    assert server_agent_triggers == agent_triggers
