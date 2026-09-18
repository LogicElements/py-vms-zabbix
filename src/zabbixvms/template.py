"""Builds the Zabbix template out of the metric catalog.

The catalog in metrics.py is the single source of truth, so the template holds
exactly the metrics the agent sends - no more and none missing. The file it writes,
data/zabbix_template.yaml, ships with the package and is what the operator imports.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import yaml

from zabbixvms import metrics
from zabbixvms.metrics import ValueType

# Export format the template is written in; it matches the server it is imported into.
EXPORT_VERSION = "7.0"

# Zabbix 6.4 renamed the section the template groups are listed in, so changing
# EXPORT_VERSION alone is not enough to move between the formats.
GROUPS_RENAMED_IN = (6, 4)

TEMPLATE_NAME = "VMS zabbix agent"
TEMPLATE_GROUP = "Templates/Applications"
TEMPLATE_FILENAME = "zabbix_template.yaml"

# Every exported object needs a uuid. Deriving them from a fixed namespace keeps them
# the same every time the template is generated, so re-importing updates the template
# instead of making a second one.
UUID_NAMESPACE = uuid.UUID("6f1d5f3a-1f1a-5a39-9f2e-6a0b0f3a9c11")

# Item type of a Zabbix trapper, which every metric of the agent is.
TRAPPER = "TRAP"

# How the value types of the catalog are spelled in an export.
EXPORT_VALUE_TYPES = {
    ValueType.FLOAT: "FLOAT",
    ValueType.UNSIGNED: "UNSIGNED",
    ValueType.CHARACTER: "CHAR",
}

STATUS_VALUE_MAP = "Stav agenta"
STATUS_MAPPINGS = (("0", "Bez chyby"), ("1", "Varování"), ("2", "Chyba"))

# Names and severities of the triggers live in the catalog in metrics.py, which
# mirrors the trigger table of the PRS.


def stable_uuid(name: str) -> str:
    """Uuid of an exported object, the same for the same name every time.

    Zabbix insists on a version 4 uuid, which is normally a random one. The value is
    derived from the name so that it does not change between generations, and then
    the version and variant bits are set to what a version 4 uuid carries.
    """
    raw = bytearray(uuid.uuid5(UUID_NAMESPACE, name).bytes)
    raw[6] = (raw[6] & 0x0F) | 0x40
    raw[8] = (raw[8] & 0x3F) | 0x80
    return uuid.UUID(bytes=bytes(raw)).hex


def groups_section(version: str = EXPORT_VERSION) -> str:
    """Name of the section the template groups are listed in for that version."""
    major, minor = (int(part) for part in version.split(".")[:2])
    return "groups" if (major, minor) < GROUPS_RENAMED_IN else "template_groups"


def template_path() -> Path:
    """Where the generated template lives inside the package."""
    return Path(__file__).parent / "data" / TEMPLATE_FILENAME


def item(metric) -> dict:
    """One item of the template, built from one metric of the catalog."""
    entry = {
        "uuid": stable_uuid(f"item:{metric.key}"),
        "name": metric.name,
        "type": TRAPPER,
        "key": metric.key,
        "value_type": EXPORT_VALUE_TYPES[metric.value_type],
        "description": metric.description,
    }
    if metric.units:
        entry["units"] = metric.units
    if metric.key == "vms.agent_status":
        entry["valuemap"] = {"name": STATUS_VALUE_MAP}
    item_triggers = triggers_of(metric.key)
    if item_triggers:
        entry["triggers"] = item_triggers
    return entry


def expression_of(trigger) -> str:
    """The condition of a trigger with the reference to its metric filled in."""
    return trigger.condition.replace(metrics.METRIC_PLACEHOLDER,
                                     f"/{TEMPLATE_NAME}/{trigger.key}")


def dependencies_of(trigger) -> list[dict]:
    """The trigger that suppresses this one, in the shape an export wants it.

    A dependency points at a trigger by the pair that identifies it, so the blocking
    one is looked up in the catalog rather than spelled out a second time.
    """
    if not trigger.blocked_by:
        return []
    blocker = metrics.trigger_named(trigger.blocked_by)
    return [{"name": blocker.name, "expression": expression_of(blocker)}]


def exported_trigger(trigger) -> dict:
    """One trigger of the catalog as the export writes it."""
    exported = {
        # Derived from what the trigger watches, not from its name, so renaming
        # one updates it on import instead of leaving the old one behind.
        "uuid": stable_uuid(f"trigger:{trigger.key}:{trigger.condition}"),
        "expression": expression_of(trigger),
        "name": trigger.name,
        "priority": trigger.priority,
    }
    dependencies = dependencies_of(trigger)
    if dependencies:
        exported["dependencies"] = dependencies
    return exported


def triggers_of(key: str) -> list[dict]:
    """Triggers of the catalog that belong under the item of that key.

    An export carries a trigger inside the item its expression reads, not beside the
    items; a template with a triggers section of its own is refused on import.
    """
    return [exported_trigger(trigger)
            for trigger in metrics.TRIGGERS if trigger.key == key]


def all_triggers() -> list[dict]:
    """Every trigger of the template, wherever in the export it sits."""
    return [trigger for metric in metrics.METRICS
            for trigger in triggers_of(metric.key)]


def build() -> dict:
    """The whole export, as the structure that is written out as YAML."""
    return {
        "zabbix_export": {
            "version": EXPORT_VERSION,
            groups_section(): [
                {"uuid": stable_uuid(f"group:{TEMPLATE_GROUP}"), "name": TEMPLATE_GROUP},
            ],
            "templates": [
                {
                    "uuid": stable_uuid(f"template:{TEMPLATE_NAME}"),
                    "template": TEMPLATE_NAME,
                    "name": TEMPLATE_NAME,
                    "description": "Metriky softwaru VMS odesílané agentem zabbixvms.",
                    "groups": [{"name": TEMPLATE_GROUP}],
                    "items": [item(metric) for metric in metrics.METRICS],
                    "macros": [
                        {"macro": macro.name, "value": macro.value,
                         "description": macro.description}
                        for macro in metrics.MACROS
                    ],
                    "valuemaps": [
                        {
                            "uuid": stable_uuid(f"valuemap:{STATUS_VALUE_MAP}"),
                            "name": STATUS_VALUE_MAP,
                            "mappings": [{"value": value, "newvalue": text}
                                         for value, text in STATUS_MAPPINGS],
                        },
                    ],
                },
            ],
        },
    }


def to_yaml() -> str:
    """The export as the text of the template file."""
    return yaml.safe_dump(build(), allow_unicode=True, sort_keys=False,
                          default_flow_style=False, width=100)


def write(path: Path | None = None) -> Path:
    """Write the template into the package and return where it went."""
    path = Path(path) if path is not None else template_path()
    path.write_text(to_yaml(), encoding="utf-8")
    return path


if __name__ == "__main__":
    print(write())
