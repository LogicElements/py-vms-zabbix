"""Catalog of the metrics the agent sends to Zabbix.

The catalog mirrors the metric tables of the PRS and is the single source of truth:
collector.py keys the collected values by it and template.py generates the Zabbix
templates from it. Names and descriptions are kept verbatim, they end up in Zabbix.

There are two catalogs, one per kind of host: METRICS, TRIGGERS and MACROS for the
host of every turbine (UC3, UC5), SERVER_METRICS, SERVER_TRIGGERS and SERVER_MACROS
for the host of the server (UC7).
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
        key="vms.raw_tables",
        name="Počet tabulek surových dat",
        value_type=ValueType.UNSIGNED,
        units="",
        description="Největší počet tabulek surových dat se stejným prefixem "
                    "přes prefixy turbíny",
    ),
    Metric(
        key="vms.raw_write_age",
        name="Stáří zápisu surových dat",
        value_type=ValueType.UNSIGNED,
        units="s",
        description="Doba od posledního zápisu do nejnovější tabulky surových dat u toho "
                    "prefixu turbíny, který je na tom nejhůř. "
                    "Hodnoty nad jeden měsíc se hlásí jako jeden měsíc.",
    ),
    Metric(
        key="vms.trend_age",
        name="Stáří trendových dat",
        value_type=ValueType.UNSIGNED,
        units="s",
        description="Doba od posledního záznamu toho ze sledovaných signálů turbíny, "
                    "který je na tom nejhůř (UC8). "
                    "Hodnoty nad jeden měsíc se hlásí jako jeden měsíc. "
                    "Turbína bez sledovaných signálů ji neodesílá.",
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

# What a standing turbine stops filling is the buffer and the raw data tables, so the
# triggers on the age of those writes wait for this one; the other sources are written
# whatever the turbine does. Any trigger that should wait too only needs this name in
# its blocked_by.
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
    ),
    Trigger(
        name="Chyba konfiguračního socketu: {ITEM.VALUE}",
        key="vms.config_age",
        condition="last({METRIC})>5m",
        priority="HIGH",
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
        # One table is being written, a second one waits for its export for a moment
        # after the switch; a third means an export did not happen.
        name="Chyba exportu surových dat: {ITEM.VALUE}",
        key="vms.raw_tables",
        condition="last({METRIC})>2",
        priority="HIGH",
    ),
    Trigger(
        name="Chyba zápisu surových dat: {ITEM.VALUE}",
        key="vms.raw_write_age",
        condition="last({METRIC})>5m",
        priority="HIGH",
        blocked_by=TURBINE_BELOW_NOMINAL,
    ),
    Trigger(
        name="Chyba trendových dat: {ITEM.VALUE}",
        key="vms.trend_age",
        condition="last({METRIC})>5m",
        priority="HIGH",
        blocked_by=TURBINE_BELOW_NOMINAL,
    ),
    Trigger(
        # The speed is the value every cycle that reads the turbine has, so its silence
        # covers a stopped agent, a database that cannot be read and a Zabbix that
        # cannot be reached alike.
        name="Z hostu nepřišla žádná hodnota 5m",
        key="vms.speed",
        condition="nodata({METRIC},5m)=1",
        priority="HIGH",
    ),
)

# The state of the agent is reported to the host of the server only.
AGENT_TRIGGERS = (
    Trigger(
        # Below AVERAGE on purpose: the trigger on vms.agent_error fires with this one and
        # carries the text, so both above the mail threshold would send two mails per fault.
        name="Agent hlásí chybu nebo varování",
        key="vms.agent_status",
        condition="last({METRIC})>0",
        priority="WARNING",
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

# Every metric of a turbine is computed from the database by the collector; the state of
# the agent is not one of them, it belongs to the host of the server.
COLLECTOR_KEYS = KEYS


# The host of the server carries what belongs to the server as a whole rather than to
# one turbine; the UPS is the first of it, and the state of the agent, which covers the
# reading of the turbines and of the server alike, is the other.
SERVER_METRICS = (
    Metric(
        key="ups.charge",
        name="Nabití baterie UPS",
        value_type=ValueType.UNSIGNED,
        units="%",
        description="Nabití baterie UPS podle IPP; při více UPS nejnižší z nich",
    ),
    Metric(
        key="vms.agent_status",
        name="Stav agenta",
        value_type=ValueType.UNSIGNED,
        units="",
        description="0 = cyklus proběhl bez chyby, 1 = varování, 2 = chyba při čtení "
                    "z databáze nebo z IPP. Popis chyby nese `vms.agent_error`.",
    ),
    Metric(
        key="vms.agent_error",
        name="Poslední chyba agenta",
        value_type=ValueType.CHARACTER,
        units="",
        description="Text poslední chyby nebo varování agenta, u turbíny s jejím názvem "
                    "na začátku; prázdný, když je vše v pořádku.",
    ),
)

SERVER_MACROS = (
    Macro(
        name="{$VMS.UPS.CHARGE.MIN}",
        value="50",
        description="Nabití baterie v %, pod kterým se hlásí chyba napájení.",
    ),
)

SERVER_TRIGGERS = (
    Trigger(
        name="Chyba napájení: {ITEM.VALUE}",
        key="ups.charge",
        condition="last({METRIC})<{$VMS.UPS.CHARGE.MIN}",
        priority="HIGH",
    ),
) + AGENT_TRIGGERS

SERVER_KEYS = tuple(metric.key for metric in SERVER_METRICS)

# The state of the agent: sent by the agent itself, to the host of the server only.
AGENT_KEYS = ("vms.agent_status", "vms.agent_error")


def by_key(key: str, catalog=METRICS) -> Metric:
    """Metric of the given key; raises KeyError for a key outside the catalog."""
    for metric in catalog:
        if metric.key == key:
            return metric
    raise KeyError(key)


def trigger_named(name: str, catalog=TRIGGERS) -> Trigger:
    """Trigger of that name; a dependency naming no trigger would be silently lost."""
    for trigger in catalog:
        if trigger.name == name:
            return trigger
    raise KeyError(name)
