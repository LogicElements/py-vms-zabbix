"""Tests of the Zabbix template: it holds exactly the metrics of the catalog, every
item is a trapper, and the value map and the triggers are in it (UC3-R4, UC5-R4)."""

import yaml

from zabbixvms import metrics
from zabbixvms.metrics import ValueType
from zabbixvms.template import (
    EXPORT_VALUE_TYPES,
    EXPORT_VERSION,
    NO_DATA_PERIOD,
    STATUS_MAPPINGS,
    STATUS_VALUE_MAP,
    TEMPLATE_GROUP,
    TEMPLATE_NAME,
    TRAPPER,
    build,
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
    """UC5-R4: 0, 1 and 2 of vms.agent_status read as text."""
    template = template_of(exported())
    value_map = template["valuemaps"][0]

    assert value_map["name"] == STATUS_VALUE_MAP
    mappings = [(m["value"], m["newvalue"]) for m in value_map["mappings"]]
    assert mappings == list(STATUS_MAPPINGS)
    assert [value for value, _ in mappings] == ["0", "1", "2"]


def test_the_status_item_uses_that_value_map():
    items = {item["key"]: item for item in template_of(exported())["items"]}

    assert items["vms.agent_status"]["valuemap"] == {"name": STATUS_VALUE_MAP}


def test_there_are_three_triggers():
    """UC5-R4: the template brings the three triggers, no more."""
    assert len(template_of(exported())["triggers"]) == 3


def test_trigger_on_a_status_above_zero():
    """UC5-R4: a state other than 0 fires."""
    expressions = [t["expression"] for t in template_of(exported())["triggers"]]

    assert f"last(/{TEMPLATE_NAME}/vms.agent_status)>0" in expressions


def test_trigger_on_a_non_empty_error_carries_the_text_in_its_name():
    """UC5-R4: the text of the error is part of the name of the trigger."""
    triggers = {t["expression"]: t for t in template_of(exported())["triggers"]}
    trigger = triggers[f"length(last(/{TEMPLATE_NAME}/vms.agent_error))>0"]

    assert "{ITEM.VALUE}" in trigger["name"]


def test_trigger_on_no_data_for_five_minutes():
    """UC5-R4: silence of five minutes fires too, which covers an agent that is down."""
    expressions = [t["expression"] for t in template_of(exported())["triggers"]]

    assert f"nodata(/{TEMPLATE_NAME}/vms.agent_status,{NO_DATA_PERIOD})=1" in expressions
    assert NO_DATA_PERIOD == "5m"


def test_every_exported_object_has_a_uuid():
    """Zabbix refuses an export whose objects have no uuid."""
    export = exported()
    template = template_of(export)

    assert export["zabbix_export"][groups_section()][0]["uuid"]
    assert template["uuid"]
    for group in (template["items"], template["triggers"], template["valuemaps"]):
        for entry in group:
            assert len(entry["uuid"]) == 32


def test_uuids_stay_the_same_between_generations():
    """A re-import updates the template instead of making a second one."""
    assert stable_uuid("item:vms.speed") == stable_uuid("item:vms.speed")
    assert stable_uuid("item:vms.speed") != stable_uuid("item:vms.info_age")


def test_building_twice_gives_the_same_template():
    assert build() == build()
