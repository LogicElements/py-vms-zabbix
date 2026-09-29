"""Builds the Zabbix templates out of the metric catalog.

The catalog in metrics.py is the single source of truth, so each template holds
exactly the metrics the agent sends to its kind of host - no more and none missing.
There are two: one for the host of every turbine and one for the host of the server.
The file it writes, data/zabbix_template.yaml, ships with the package and is what the
operator imports.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
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
SERVER_TEMPLATE_NAME = "VMS zabbix agent server"
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

STATUS_KEY = "vms.agent_status"
STATUS_VALUE_MAP = "Stav agenta"
STATUS_MAPPINGS = (("0", "Bez chyby"), ("1", "Varování"), ("2", "Chyba"))

# Names and severities of the triggers live in the catalog in metrics.py, which
# mirrors the trigger tables of the PRS.


@dataclass(frozen=True)
class Template:
    """One template of the export and the catalog it is built from."""

    name: str
    description: str
    metrics: tuple
    triggers: tuple
    macros: tuple
    # Put in front of the names the uuids are derived from, so that an object of one
    # template never shares a uuid with one of the other. The template of the turbines
    # keeps the plain names it was first exported with, so a re-import still updates
    # it in place.
    uuid_scope: str = ""

    def uuid_of(self, name: str) -> str:
        return stable_uuid(f"{self.uuid_scope}:{name}" if self.uuid_scope else name)


TURBINES = Template(
    name=TEMPLATE_NAME,
    description="Metriky softwaru VMS odesílané agentem zabbixvms.",
    metrics=metrics.METRICS,
    triggers=metrics.TRIGGERS,
    macros=metrics.MACROS,
)

SERVER = Template(
    name=SERVER_TEMPLATE_NAME,
    description="Metriky serveru VMS odesílané agentem zabbixvms, společné všem turbínám "
                "na serveru.",
    metrics=metrics.SERVER_METRICS,
    triggers=metrics.SERVER_TRIGGERS,
    macros=metrics.SERVER_MACROS,
    uuid_scope="server",
)

TEMPLATES = (TURBINES, SERVER)


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


def item(metric, template: Template = TURBINES) -> dict:
    """One item of the template, built from one metric of the catalog."""
    entry = {
        "uuid": template.uuid_of(f"item:{metric.key}"),
        "name": metric.name,
        "type": TRAPPER,
        "key": metric.key,
        "value_type": EXPORT_VALUE_TYPES[metric.value_type],
        "description": metric.description,
    }
    if metric.units:
        entry["units"] = metric.units
    if metric.key == STATUS_KEY:
        entry["valuemap"] = {"name": STATUS_VALUE_MAP}
    item_triggers = triggers_of(metric.key, template)
    if item_triggers:
        entry["triggers"] = item_triggers
    return entry


def expression_of(trigger, template: Template = TURBINES) -> str:
    """The condition of a trigger with the reference to its metric filled in."""
    return trigger.condition.replace(metrics.METRIC_PLACEHOLDER,
                                     f"/{template.name}/{trigger.key}")


def dependencies_of(trigger, template: Template = TURBINES) -> list[dict]:
    """The trigger that suppresses this one, in the shape an export wants it.

    A dependency points at a trigger by the pair that identifies it, so the blocking
    one is looked up in the catalog rather than spelled out a second time.
    """
    if not trigger.blocked_by:
        return []
    blocker = metrics.trigger_named(trigger.blocked_by, template.triggers)
    return [{"name": blocker.name, "expression": expression_of(blocker, template)}]


def exported_trigger(trigger, template: Template = TURBINES) -> dict:
    """One trigger of the catalog as the export writes it."""
    exported = {
        # Derived from what the trigger watches, not from its name, so renaming
        # one updates it on import instead of leaving the old one behind.
        "uuid": template.uuid_of(f"trigger:{trigger.key}:{trigger.condition}"),
        "expression": expression_of(trigger, template),
        "name": trigger.name,
        "priority": trigger.priority,
    }
    dependencies = dependencies_of(trigger, template)
    if dependencies:
        exported["dependencies"] = dependencies
    return exported


def triggers_of(key: str, template: Template = TURBINES) -> list[dict]:
    """Triggers of the catalog that belong under the item of that key.

    An export carries a trigger inside the item its expression reads, not beside the
    items; a template with a triggers section of its own is refused on import.
    """
    return [exported_trigger(trigger, template)
            for trigger in template.triggers if trigger.key == key]


def all_triggers(template: Template = TURBINES) -> list[dict]:
    """Every trigger of the template, wherever in the export it sits."""
    return [trigger for metric in template.metrics
            for trigger in triggers_of(metric.key, template)]


def exported_template(template: Template) -> dict:
    """One template of the export, with its items, macros and value map."""
    exported = {
        "uuid": stable_uuid(f"template:{template.name}"),
        "template": template.name,
        "name": template.name,
        "description": template.description,
        "groups": [{"name": TEMPLATE_GROUP}],
        "items": [item(metric, template) for metric in template.metrics],
        "macros": [
            {"macro": macro.name, "value": macro.value, "description": macro.description}
            for macro in template.macros
        ],
    }
    # The value map translates the state of the agent, which only the server reports.
    if any(metric.key == STATUS_KEY for metric in template.metrics):
        exported["valuemaps"] = [
            {
                "uuid": template.uuid_of(f"valuemap:{STATUS_VALUE_MAP}"),
                "name": STATUS_VALUE_MAP,
                "mappings": [{"value": value, "newvalue": text}
                             for value, text in STATUS_MAPPINGS],
            },
        ]
    return exported


def build() -> dict:
    """The whole export, as the structure that is written out as YAML."""
    return {
        "zabbix_export": {
            "version": EXPORT_VERSION,
            groups_section(): [
                {"uuid": stable_uuid(f"group:{TEMPLATE_GROUP}"), "name": TEMPLATE_GROUP},
            ],
            "templates": [exported_template(template) for template in TEMPLATES],
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
