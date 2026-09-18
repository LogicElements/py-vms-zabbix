"""Catalog of the metrics the agent sends to Zabbix.

The catalog mirrors the metric table of the PRS and is the single source of truth:
collector.py keys the collected values by it and template.py generates the Zabbix
template from it. Names and descriptions are kept verbatim, they end up in Zabbix.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ValueType(Enum):
    """Value type of a Zabbix item, named the way Zabbix names it."""

    FLOAT = "Numeric (float)"
    UNSIGNED = "Numeric (unsigned)"
    CHARACTER = "Character"


@dataclass(frozen=True)
class Metric:
    """One metric: everything a Zabbix trapper item needs to be created from it."""

    key: str
    name: str
    value_type: ValueType
    units: str
    description: str


METRICS = (
    Metric(
        key="vms.speed",
        name="Otáčky turbíny",
        value_type=ValueType.FLOAT,
        units="rpm",
        description="Aktuální otáčky turbíny",
    ),
    Metric(
        key="vms.info_age",
        name="Stáří info záznamu",
        value_type=ValueType.UNSIGNED,
        units="s",
        description="Doba od poslední aktualizace tabulky `info`. "
                    "Hodnoty nad jeden měsíc se hlásí jako jeden měsíc.",
    ),
    Metric(
        key="vms.timestamp_age",
        name="Stáří timestamp dat",
        value_type=ValueType.UNSIGNED,
        units="s",
        description="Doba od posledních přijatých timestamp dat. "
                    "Hodnoty nad jeden měsíc se hlásí jako jeden měsíc.",
    ),
    Metric(
        key="vms.config_age",
        name="Stáří konfiguračních dat",
        value_type=ValueType.UNSIGNED,
        units="s",
        description="Doba od posledních přijatých konfiguračních dat. "
                    "Hodnoty nad jeden měsíc se hlásí jako jeden měsíc.",
    ),
    Metric(
        key="vms.buf_rows",
        name="Počet řádků v bufferech",
        value_type=ValueType.UNSIGNED,
        units="",
        description="Součet počtu řádků přes bufferové tabulky turbíny",
    ),
    Metric(
        key="vms.buf_age",
        name="Stáří bufferů",
        value_type=ValueType.UNSIGNED,
        units="s",
        description="Doba od posledních dat přijatých do toho bufferu turbíny, který je "
                    "na tom nejhůř. Hodnoty nad jeden měsíc se hlásí jako jeden měsíc.",
    ),
    Metric(
        key="vms.buf_bulk",
        name="Doba bulk zápisu",
        value_type=ValueType.UNSIGNED,
        units="ms",
        description="Součet doby zápisu bulk příkazů do databáze přes buffery turbíny",
    ),
    Metric(
        key="vms.agent_status",
        name="Stav agenta",
        value_type=ValueType.UNSIGNED,
        units="",
        description="0 = agent pracuje bez chyby, 1 = varování, 2 = chyba. "
                    "Popis chyby nese `vms.agent_error`.",
    ),
    Metric(
        key="vms.agent_error",
        name="Poslední chyba agenta",
        value_type=ValueType.CHARACTER,
        units="",
        description="Text poslední chyby nebo varování agenta; prázdný, "
                    "když je vše v pořádku.",
    ),
)

@dataclass(frozen=True)
class Macro:
    """One macro of the template, as its row of the macro table in the PRS."""

    name: str
    value: str
    description: str


# A macro keeps a threshold out of the conditions, so a turbine that runs at another
# speed only needs the value overridden on its host, not a template of its own.
MACROS = (
    Macro(
        name="{$VMS.SPEED.NOMINAL}",
        value="2500",
        description="Otáčky, pod kterými se turbína nepovažuje za běžící.",
    ),
)


@dataclass(frozen=True)
class Trigger:
    """One trigger of the template, as its row of the trigger table in the PRS."""

    name: str
    key: str
    condition: str
    priority: str
    # Name of the trigger that suppresses this one while it is itself firing.
    blocked_by: str = ""


# What the condition writes instead of the reference to the metric.
METRIC_PLACEHOLDER = "{METRIC}"

# A standing turbine writes no measurements, so the triggers on the age of what it
# measures stay quiet while this one fires. The setup database is written whatever the
# turbine does, so the trigger on its age is not among them.
TURBINE_BELOW_NOMINAL = "Turbína pod nominálními otáčkami: {ITEM.VALUE}"

# The triggers mirror the trigger table of the PRS. The key decides which item of the
# template the trigger ends up under, which is where an export keeps its triggers.
TRIGGERS = (
    Trigger(
        name=TURBINE_BELOW_NOMINAL,
        key="vms.speed",
        condition="last({METRIC})<{$VMS.SPEED.NOMINAL}",
        priority="AVERAGE",
    ),
    Trigger(
        name="Chyba databáze VMS setupu: {ITEM.VALUE}",
        key="vms.info_age",
        condition="last({METRIC})>5m",
        priority="HIGH",
    ),
    Trigger(
        name="Chyba timestamp socketu: {ITEM.VALUE}",
        key="vms.timestamp_age",
        condition="last({METRIC})>5m",
        priority="HIGH",
        blocked_by=TURBINE_BELOW_NOMINAL,
    ),
    Trigger(
        name="Chyba konfiguračního socketu: {ITEM.VALUE}",
        key="vms.config_age",
        condition="last({METRIC})>5m",
        priority="HIGH",
        blocked_by=TURBINE_BELOW_NOMINAL,
    ),
    Trigger(
        name="Chyba SW analýzy čtení bufferu: {ITEM.VALUE}",
        key="vms.buf_rows",
        condition="last({METRIC})>100000",
        priority="HIGH",
    ),
    Trigger(
        name="Chyba ukládání do bufferu: {ITEM.VALUE}",
        key="vms.buf_age",
        condition="last({METRIC})>5m",
        priority="HIGH",
        blocked_by=TURBINE_BELOW_NOMINAL,
    ),
    Trigger(
        name="Agent hlásí chybu nebo varování",
        key="vms.agent_status",
        condition="last({METRIC})>0",
        priority="AVERAGE",
    ),
    Trigger(
        name="Z hostu nepřišla žádná hodnota 5m",
        key="vms.agent_status",
        condition="nodata({METRIC},5m)=1",
        priority="HIGH",
    ),
    Trigger(
        name="Chyba agenta: {ITEM.VALUE}",
        key="vms.agent_error",
        condition="length(last({METRIC}))>0",
        priority="AVERAGE",
    ),
)

KEYS = tuple(metric.key for metric in METRICS)

# The split follows the Zdroj column of the source table in the PRS: the agent reports
# its own state itself, the rest is computed from the database by the collector.
AGENT_KEYS = ("vms.agent_status", "vms.agent_error")
COLLECTOR_KEYS = tuple(key for key in KEYS if key not in AGENT_KEYS)


def by_key(key: str) -> Metric:
    """Metric of the given key; raises KeyError for a key outside the catalog."""
    for metric in METRICS:
        if metric.key == key:
            return metric
    raise KeyError(key)


def trigger_named(name: str) -> Trigger:
    """Trigger of that name; a dependency naming no trigger would be silently lost."""
    for trigger in TRIGGERS:
        if trigger.name == name:
            return trigger
    raise KeyError(name)
