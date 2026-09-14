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
        value_type=ValueType.FLOAT,
        units="s",
        description="Doba od poslední aktualizace tabulky `info`. "
                    "Hodnota -1 znamená, že údaj není k dispozici.",
    ),
    Metric(
        key="vms.timestamp_age",
        name="Stáří timestamp dat",
        value_type=ValueType.FLOAT,
        units="s",
        description="Doba od posledních přijatých timestamp dat. "
                    "Hodnota -1 znamená, že údaj není k dispozici.",
    ),
    Metric(
        key="vms.config_age",
        name="Stáří konfiguračních dat",
        value_type=ValueType.FLOAT,
        units="s",
        description="Doba od posledních přijatých konfiguračních dat. "
                    "Hodnota -1 znamená, že údaj není k dispozici.",
    ),
    Metric(
        key="vms.buf_rows_1",
        name="Počet řádků v bufferu 1",
        value_type=ValueType.UNSIGNED,
        units="",
        description="Počet řádků v první bufferové tabulce",
    ),
    Metric(
        key="vms.buf_rows_2",
        name="Počet řádků v bufferu 2",
        value_type=ValueType.UNSIGNED,
        units="",
        description="Počet řádků v druhé bufferové tabulce",
    ),
    Metric(
        key="vms.buf_age_1",
        name="Stáří bufferu 1",
        value_type=ValueType.FLOAT,
        units="s",
        description="Doba od posledních dat přijatých do bufferu 1. "
                    "Hodnota -1 znamená, že údaj není k dispozici.",
    ),
    Metric(
        key="vms.buf_age_2",
        name="Stáří bufferu 2",
        value_type=ValueType.FLOAT,
        units="s",
        description="Doba od posledních dat přijatých do bufferu 2. "
                    "Hodnota -1 znamená, že údaj není k dispozici.",
    ),
    Metric(
        key="vms.buf_bulk_1",
        name="Doba bulk zápisu 1",
        value_type=ValueType.UNSIGNED,
        units="ms",
        description="Doba zápisu bulk příkazu do databáze pro buffer 1",
    ),
    Metric(
        key="vms.buf_bulk_2",
        name="Doba bulk zápisu 2",
        value_type=ValueType.UNSIGNED,
        units="ms",
        description="Doba zápisu bulk příkazu do databáze pro buffer 2",
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
