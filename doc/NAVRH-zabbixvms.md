# Návrh struktury balíčku `zabbixvms`

Členění kódu, jména modulů a tříd. Co má agent dělat, popisuje [PRS](PRS-zabbixvms.md).

## Jména

| Co | Jméno |
| --- | --- |
| Distribuce | `zabbixvms` |
| Importovaný balíček | `zabbixvms` |
| Služba Windows | `ZabbixVms` |
| Vstupní bod služby | `zabbixvms-service` |
| Vstupní bod tray aplikace | `zabbixvms-tray` |

Moduly se jmenují malými písmeny, třídy v CapWords, takže se jméno modulu a jméno třídy v něm
nepřekrývají.

## Struktura

```
src/zabbixvms/
    __init__.py          jen __version__, nic se nereexportuje
    config.py            Config, ZabbixConfig, DatabaseConfig, Turbine
    log.py               logovací soubor s rotací a zápis do Windows Event Logu
    metrics.py           Metric, ValueType, METRICS – katalog metrik
    collector.py         Collector – čte BVMS a počítá hodnoty metrik
    sender.py            TrapperSender – odesílá hodnoty do Zabbixu
    agent.py             Agent – cyklus sběr → odeslání → prodleva
    service.py           ZabbixVmsService – služba Windows a její registrace
    servicecontrol.py    ServiceController – dotaz na stav a ovládání služby
    tray.py              TrayApp – ikona v systray a její kontextové menu
    template.py          generátor šablony pro Zabbix z katalogu metrik
    data/
        config_default.json   výchozí konfigurace nasazovaná do ProgramData
        zabbix_template.yaml  šablona pro import do Zabbixu, generovaná template.py
```

## Odpovědnosti modulů

| Modul | Odpovědnost | Requirementy |
| --- | --- | --- |
| `config.py` | načtení a uložení konfigurace, cesta do `ProgramData`, nasazení výchozí konfigurace z balíčku, kontrola rozsahů | UC2-R1 až UC2-R8 |
| `log.py` | logovací soubor vedle konfigurace, rotace, souběžný zápis služby i tray aplikace, zápis do Event Logu | UC5-R1, UC5-R2 |
| `metrics.py` | definice metrik: klíč, název, typ hodnoty, jednotka, popis | UC3-R1, UC3-R2 |
| `collector.py` | čtení řádku informační tabulky a počtů řádků bufferů, výpočet hodnot | UC4-R1 až UC4-R5 |
| `sender.py` | odeslání hodnot trapperem pod hostem `<location>_<turbína>`, kontrola odmítnutých hodnot | UC2-R2, UC2-R5 |
| `agent.py` | cyklus přes turbíny, prodleva mezi cykly, pokračování po chybě cyklu | UC1-R4, UC4-R6 |
| `service.py` | registrace a odregistrace služby, automatický start, oprávnění k ovládání | UC1-R2, UC1-R3, UC1-R7 |
| `servicecontrol.py` | zjištění stavu služby a její spuštění, zastavení a restart | UC1-R5, UC1-R6 |
| `tray.py` | ikona podle stavu služby, kontextové menu včetně otevření konfigurace | UC1-R5, UC1-R6, UC1-R8, UC2-R8 |
| `template.py` | šablona pro Zabbix vygenerovaná z katalogu metrik | UC3-R4 |

## Rozhodnutí

### Katalog metrik je jediný zdroj pravdy

Definice metrik žijí v `metrics.py`. `collector.py` podle nich klíčuje spočítané hodnoty a
`template.py` z nich generuje šablonu pro Zabbix. UC3-R1 požaduje, aby agent odesílal právě
metriky z tabulky v PRS – s tímto uspořádáním to ověří test, který porovná klíče z `collector.py`
a ze šablony proti `METRICS`.

### Jeden balíček, dva procesy

Služba běží v session 0 a nemá přístup k desktopu, tray aplikace běží v sezení přihlášeného
uživatele. Jsou to dva vstupní body nad společným `config.py` a `servicecontrol.py`, ne dvě
distribuce.

### Ikona v systray stojí na pywin32

Tray aplikace staví ikonu přes `Shell_NotifyIcon` z balíčku `pywin32`, který je v závislostech
kvůli službě. Nepřidává se tím žádná další závislost. Volba se může při implementaci upřesnit.

### Práce s databází je součástí balíčku

Agent nezávisí na balíčku `pyvms`. Používaly se z něj dva dotazy, které přebírá `collector.py`:

- řádek informační tabulky pro jednu turbínu, vybraný podle `SystemId`,
- počty řádků bufferových tabulek z `information_schema.TABLES` pro danou databázi.

Sloupce se v obou dotazech vyjmenovávají, nepoužívá se `SELECT *` – tím je splněné UC4-R3, aniž
by se hodnoty dohledávaly podle pozice. Z `information_schema` se čte jen `TABLE_ROWS`;
`UPDATE_TIME` není potřeba, protože stáří bufferu pochází ze sloupců `Date_Buffer_1` a
`Date_Buffer_2` informační tabulky.
