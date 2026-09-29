"""Tests of the Zabbix templates: each holds exactly the metrics of its catalog, every
item is a trapper, and the value map and the triggers are in it (UC3-R4, UC5-R4,
UC7-R5, UC7-R6)."""

import yaml

from zabbixvms import metrics
from zabbixvms.metrics import ValueType
from zabbixvms.template import (
    EXPORT_VALUE_TYPES,
    EXPORT_VERSION,
    STATUS_MAPPINGS,
    STATUS_VALUE_MAP,
    SERVER_TEMPLATE_NAME,
    TEMPLATE_GROUP,
    TEMPLATE_NAME,
    TRAPPER,
    all_triggers,
    build,
    exported_trigger,
    groups_section,
    stable_uuid,
    template_path,
    to_yaml,
)


def exported():
    """The template as it is shipped in the package."""
    return yaml.safe_load(template_path().read_text(encoding="utf-8"))


def template_of(export):
    return export["zabbix_export"]["templates"][0]


def exported_triggers():
    """Every trigger of the shipped template, read from inside its items."""
    return [trigger for item in template_of(exported())["items"]
            for trigger in item.get("triggers", [])]


def test_triggers_sit_inside_their_items():
    """An export has no triggers section of its own; the import refuses one."""
    template = template_of(exported())

    assert "triggers" not in template
    keys_with_triggers = {item["key"] for item in template["items"]
                          if item.get("triggers")}
    assert keys_with_triggers == {trigger.key for trigger in metrics.TRIGGERS}


def test_each_trigger_sits_under_an_item_its_expression_reads():
    """Zabbix places a trigger under the item it refers to."""
    for item in template_of(exported())["items"]:
        for trigger in item.get("triggers", []):
            assert f"/{TEMPLATE_NAME}/{item['key']}" in trigger["expression"]


def test_the_file_in_the_package_is_what_the_generator_builds():
    """The shipped template cannot go stale against the catalog."""
    assert template_path().read_text(encoding="utf-8") == to_yaml()


def test_template_is_valid_yaml_with_the_export_around_it():
    """UC3-R4: Zabbix can read the file."""
    export = exported()

    assert export["zabbix_export"]["version"] == EXPORT_VERSION
    assert template_of(export)["template"] == TEMPLATE_NAME


def test_the_groups_are_listed_the_way_the_version_wants():
    """Zabbix 6.4 renamed the section, so the version decides what it is called."""
    assert groups_section("6.0") == "groups"
    assert groups_section("6.2") == "groups"
    assert groups_section("6.4") == "template_groups"
    assert groups_section("7.0") == "template_groups"


def test_the_export_carries_the_group_section_of_its_own_version():
    export = exported()["zabbix_export"]

    assert groups_section() in export
    assert export[groups_section()][0]["name"] == TEMPLATE_GROUP
    # Inside a template the reference is called groups in every version.
    assert template_of(exported())["groups"][0]["name"] == TEMPLATE_GROUP


def test_items_are_exactly_the_metrics_of_the_catalog():
    """UC3-R4: nothing extra and nothing missing against the table in the PRS."""
    keys = [item["key"] for item in template_of(exported())["items"]]

    assert keys == list(metrics.KEYS)


def test_every_item_is_a_trapper():
    """UC3-R4: all metrics arrive as Zabbix trapper items."""
    for item in template_of(exported())["items"]:
        assert item["type"] == TRAPPER


def test_items_carry_the_name_type_and_unit_of_the_catalog():
    """UC3-R4: an item is created from the catalog row, with nothing filled in by hand."""
    items = {item["key"]: item for item in template_of(exported())["items"]}

    for metric in metrics.METRICS:
        item = items[metric.key]
        assert item["name"] == metric.name
        assert item["value_type"] == EXPORT_VALUE_TYPES[metric.value_type]
        assert item.get("units", "") == metric.units
        assert item["description"] == metric.description


def test_value_types_are_the_ones_zabbix_knows():
    assert set(EXPORT_VALUE_TYPES) == set(ValueType)
    assert set(EXPORT_VALUE_TYPES.values()) == {"FLOAT", "UNSIGNED", "CHAR"}


def test_status_has_a_value_map_of_its_three_values():
    """UC5-R4: 0, 1 and 2 of vms.agent_status read as text, in the template of the
    server, which is the one that has the status."""
    template = server_template_of(exported())
    value_map = template["valuemaps"][0]

    assert value_map["name"] == STATUS_VALUE_MAP
    mappings = [(m["value"], m["newvalue"]) for m in value_map["mappings"]]
    assert mappings == list(STATUS_MAPPINGS)
    assert [value for value, _ in mappings] == ["0", "1", "2"]


def test_the_status_item_uses_that_value_map():
    items = {item["key"]: item for item in server_template_of(exported())["items"]}

    assert items["vms.agent_status"]["valuemap"] == {"name": STATUS_VALUE_MAP}


def test_the_template_of_the_turbines_has_no_state_of_the_agent():
    """UC3-R4, UC5-R4: the state is reported to the host of the server, so the template
    of the turbines holds neither its items, nor a value map for them."""
    template = template_of(exported())

    assert not set(metrics.AGENT_KEYS) & {item["key"] for item in template["items"]}
    assert "valuemaps" not in template


def test_the_template_brings_the_triggers_of_the_catalog():
    """UC5-R4: every trigger of the table reaches the template, and no other."""
    exported = exported_triggers()

    assert len(exported) == len(metrics.TRIGGERS)
    assert {trigger["name"] for trigger in exported} == \
        {trigger.name for trigger in metrics.TRIGGERS}


def test_silence_weighs_more_than_a_reported_error():
    """A host that says nothing may be a host whose agent is not running.

    The gap widened once mail was set up for AVERAGE and above: the reported error is
    below that threshold, silence well above it.
    """
    priorities = {t["name"]: t["priority"] for t in server_triggers()}

    assert priorities["Z hostu nepřišla žádná hodnota 5m"] == "HIGH"
    assert priorities["Agent hlásí chybu nebo varování"] == "WARNING"


def test_trigger_on_a_status_above_zero():
    """UC5-R4: a state other than 0 fires, on the host of the server."""
    expressions = [t["expression"] for t in server_triggers()]

    assert f"last(/{SERVER_TEMPLATE_NAME}/vms.agent_status)>0" in expressions


def test_trigger_on_a_non_empty_error_carries_the_text_in_its_name():
    """UC5-R4: the text of the error is part of the name of the trigger."""
    triggers = {t["expression"]: t for t in server_triggers()}
    trigger = triggers[f"length(last(/{SERVER_TEMPLATE_NAME}/vms.agent_error))>0"]

    assert "{ITEM.VALUE}" in trigger["name"]


def test_trigger_on_no_data_for_five_minutes():
    """UC5-R4: silence of five minutes fires on the server, which covers an agent that
    is down."""
    expressions = [t["expression"] for t in server_triggers()]

    assert f"nodata(/{SERVER_TEMPLATE_NAME}/vms.agent_status,5m)=1" in expressions


def test_a_turbine_that_sends_no_speed_for_five_minutes_is_a_problem():
    """UC5-R4: the turbine has no state of the agent to wait for, so it is its speed
    that has to keep coming."""
    triggers = {t["expression"]: t for t in exported_triggers()}
    trigger = triggers[f"nodata(/{TEMPLATE_NAME}/vms.speed,5m)=1"]

    assert trigger["name"] == "Z hostu nepřišla žádná hodnota 5m"
    assert trigger["priority"] == "HIGH"


def test_every_exported_object_has_a_uuid():
    """Zabbix refuses an export whose objects have no uuid."""
    export = exported()
    template = template_of(export)

    assert export["zabbix_export"][groups_section()][0]["uuid"]
    assert template["uuid"]
    for group in (template["items"], exported_triggers(),
                  server_template_of(export)["valuemaps"]):
        for entry in group:
            assert len(entry["uuid"]) == 32


def test_uuids_stay_the_same_between_generations():
    """A re-import updates the template instead of making a second one."""
    assert stable_uuid("item:vms.speed") == stable_uuid("item:vms.speed")
    assert stable_uuid("item:vms.speed") != stable_uuid("item:vms.info_age")


def test_every_uuid_is_version_four():
    """Zabbix refuses anything else: Invalid parameter "/1/uuid": UUIDv4 is expected."""
    import uuid as uuid_module

    export = exported()
    template = template_of(export)
    everything = ([export["zabbix_export"][groups_section()][0], template]
                  + template["items"] + exported_triggers()
                  + server_template_of(export)["valuemaps"])

    for entry in everything:
        parsed = uuid_module.UUID(entry["uuid"])
        assert parsed.version == 4, entry.get("key") or entry.get("name")
        assert parsed.variant == uuid_module.RFC_4122


def test_building_twice_gives_the_same_template():
    assert build() == build()


def test_the_template_declares_the_macros_of_the_catalog():
    """UC5-R4: a threshold kept in a macro can be overridden on a single host."""
    declared = template_of(build())["macros"]

    assert declared == [
        {"macro": macro.name, "value": macro.value, "description": macro.description}
        for macro in metrics.MACROS
    ]


def test_the_shipped_template_declares_the_macros_too():
    """UC5-R4: the file in the package is what gets imported, not what build() returns."""
    assert template_of(exported())["macros"] == template_of(build())["macros"]


def test_a_blocked_trigger_points_at_the_one_that_blocks_it():
    """UC5-R4: the dependency names the blocking trigger and repeats its expression."""
    blocked = [trigger for trigger in metrics.TRIGGERS if trigger.blocked_by]
    assert blocked, "the check needs at least one dependent trigger"

    exported_by_name = {trigger["name"]: trigger for trigger in all_triggers()}
    for trigger in blocked:
        blocker = metrics.trigger_named(trigger.blocked_by)
        dependencies = exported_by_name[trigger.name]["dependencies"]

        assert dependencies == [{"name": blocker.name,
                                 "expression": exported_by_name[blocker.name]["expression"]}]


def test_a_trigger_nothing_blocks_carries_no_dependency():
    """An empty dependencies section would only be noise in the export."""
    for trigger in metrics.TRIGGERS:
        if not trigger.blocked_by:
            assert "dependencies" not in {**exported_trigger(trigger)}


def test_the_shipped_template_carries_the_dependencies():
    """UC5-R4: the dependency has to survive into the file that is imported."""
    shipped = {trigger["name"]: trigger
               for item in template_of(exported())["items"]
               for trigger in item.get("triggers", [])}

    for trigger in metrics.TRIGGERS:
        if trigger.blocked_by:
            assert shipped[trigger.name]["dependencies"][0]["name"] == trigger.blocked_by


def server_template_of(export):
    """The template of the server host, the second one of the export."""
    return next(template for template in export["zabbix_export"]["templates"]
                if template["template"] == SERVER_TEMPLATE_NAME)


def server_triggers():
    """Every trigger of the shipped server template, read from inside its items."""
    return [trigger for item in server_template_of(exported())["items"]
            for trigger in item.get("triggers", [])]


def every_uuid(export):
    """Every uuid of the export, wherever it sits."""
    found = [group["uuid"] for group in export["zabbix_export"][groups_section()]]
    for template in export["zabbix_export"]["templates"]:
        found.append(template["uuid"])
        for item in template["items"]:
            found.append(item["uuid"])
            found.extend(trigger["uuid"] for trigger in item.get("triggers", []))
        found.extend(value_map["uuid"] for value_map in template.get("valuemaps", []))
    return found


def test_the_export_holds_the_template_of_the_turbines_and_of_the_server():
    """UC7-R5: a second template beside the one of the turbines, which stays first."""
    names = [template["template"] for template in exported()["zabbix_export"]["templates"]]

    assert names == [TEMPLATE_NAME, SERVER_TEMPLATE_NAME]
    assert SERVER_TEMPLATE_NAME == "VMS zabbix agent server"


def test_the_server_template_holds_exactly_the_metrics_of_its_catalog():
    """UC7-R5: nothing extra and nothing missing against the table in UC7."""
    items = server_template_of(exported())["items"]

    assert [item["key"] for item in items] == list(metrics.SERVER_KEYS)
    for item, metric in zip(items, metrics.SERVER_METRICS):
        assert item["type"] == TRAPPER
        assert item["name"] == metric.name
        assert item["value_type"] == EXPORT_VALUE_TYPES[metric.value_type]
        assert item.get("units", "") == metric.units
        assert item["description"] == metric.description


def test_the_server_template_brings_the_triggers_of_its_catalog():
    """UC7-R5: every trigger of the table in UC7, each under the item it reads."""
    template = server_template_of(exported())

    assert sorted(trigger["name"] for trigger in server_triggers()) == \
        sorted(trigger.name for trigger in metrics.SERVER_TRIGGERS)
    for item in template["items"]:
        for trigger in item.get("triggers", []):
            assert f"/{SERVER_TEMPLATE_NAME}/{item['key']}" in trigger["expression"]
            assert f"/{TEMPLATE_NAME}/" not in trigger["expression"]


def test_the_power_fails_below_the_macro_of_the_server_template():
    """UC7-R6: the expression reads the charge of this template against its macro."""
    expressions = {trigger["name"]: trigger["expression"] for trigger in server_triggers()}

    assert expressions["Chyba napájení: {ITEM.VALUE}"] == \
        f"last(/{SERVER_TEMPLATE_NAME}/ups.charge)<{{$VMS.UPS.CHARGE.MIN}}"


def test_the_server_template_declares_its_macro():
    """UC7-R6: the limit of 50 % can be overridden on the host of the server."""
    assert server_template_of(exported())["macros"] == [
        {"macro": macro.name, "value": macro.value, "description": macro.description}
        for macro in metrics.SERVER_MACROS
    ]


def test_the_server_template_maps_the_state_of_the_agent_to_text():
    """UC7-R5: the same value map as the turbines have, in a template of its own."""
    template = server_template_of(exported())
    items = {item["key"]: item for item in template["items"]}

    assert [(m["value"], m["newvalue"]) for m in template["valuemaps"][0]["mappings"]] == \
        list(STATUS_MAPPINGS)
    assert items["vms.agent_status"]["valuemap"] == {"name": STATUS_VALUE_MAP}


def test_every_uuid_of_the_export_is_its_own():
    """Both templates hold a trigger on silence; a uuid shared between them would make
    the import take one object for the other."""
    found = every_uuid(exported())

    assert len(found) == len(set(found))


def test_the_uuids_of_the_server_template_are_version_four_too():
    import uuid as uuid_module

    for value in every_uuid(exported()):
        parsed = uuid_module.UUID(value)
        assert parsed.version == 4
        assert parsed.variant == uuid_module.RFC_4122


def test_the_template_of_the_turbines_keeps_its_uuids():
    """UC7-R5: the template of the turbines does not change, so a re-import of the new
    file updates it in place instead of making its objects anew."""
    template = template_of(exported())

    for item in template["items"]:
        assert item["uuid"] == stable_uuid(f"item:{item['key']}")
        for trigger in item.get("triggers", []):
            condition = next(t.condition for t in metrics.TRIGGERS if t.name == trigger["name"])
            assert trigger["uuid"] == stable_uuid(f"trigger:{item['key']}:{condition}")
    assert template["uuid"] == stable_uuid(f"template:{TEMPLATE_NAME}")


def test_the_template_of_the_turbines_knows_nothing_of_the_server():
    """UC7-R5: the metrics, triggers and macro of the server stay out of it."""
    template = template_of(exported())

    assert "ups.charge" not in [item["key"] for item in template["items"]]
    assert "{$VMS.UPS.CHARGE.MIN}" not in [macro["macro"] for macro in template["macros"]]
