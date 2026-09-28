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
    metrics.py           Metric, ValueType, METRICS, Trigger, TRIGGERS – katalogy
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
| `config.py` | načtení a uložení konfigurace, cesta do `ProgramData`, nasazení výchozí konfigurace z balíčku, kontrola rozsahů a prefixů surových dat, doplnění položek z novějších verzí v paměti i do souboru | UC2-R1 až UC2-R10, UC6-R1 |
| `log.py` | logovací soubor vedle konfigurace, rotace, souběžný zápis služby i tray aplikace, zápis do Event Logu | UC5-R1, UC5-R2 |
| `metrics.py` | definice metrik: klíč, název, typ hodnoty, jednotka, popis; definice triggerů: název, klíč metriky, podmínka, priorita | UC3-R1, UC3-R2, UC5-R4 |
| `collector.py` | čtení řádku informační tabulky, počtů řádků bufferů a tabulek surových dat, výpočet hodnot | UC4-R1 až UC4-R5, UC4-R7, UC4-R8, UC6-R2 až UC6-R5 |
| `sender.py` | odeslání hodnot trapperem pod hostem `<location>_<turbína>`, kontrola odmítnutých hodnot | UC2-R2, UC2-R5 |
| `agent.py` | cyklus přes turbíny, prodleva mezi cykly, pokračování po chybě cyklu | UC1-R4, UC4-R6 |
| `service.py` | registrace a odregistrace služby, automatický start, oprávnění k ovládání, příkaz `complete-config` pro aktualizaci | UC1-R2, UC1-R3, UC1-R7, UC2-R10 |
| `servicecontrol.py` | zjištění stavu služby a její spuštění, zastavení a restart | UC1-R5, UC1-R6 |
| `tray.py` | ikona podle stavu služby, kontextové menu včetně otevření datové složky | UC1-R5, UC1-R6, UC1-R8, UC2-R8 |
| `template.py` | šablona pro Zabbix vygenerovaná z katalogů metrik a triggerů | UC3-R4, UC5-R4 |

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
by se hodnoty dohledávaly podle pozice. U bufferů se z `information_schema` čte jen
`TABLE_ROWS`; `UPDATE_TIME` není potřeba, protože stáří bufferu pochází ze sloupců
`Date_Buffer_1` a `Date_Buffer_2` informační tabulky.

Třetí dotaz, na tabulky surových dat (UC6), už v `pyvms` neměl předlohu. Pro všechny prefixy
turbíny se ptá jednou, na `TABLE_NAME`, `CREATE_TIME` a `UPDATE_TIME`
z `information_schema.TABLES`, se vzorem `LIKE` pro každý prefix. Podtržítko je ve vzoru
`LIKE` zástupný znak, takže se escapuje (`btt\_tg1\_%`); jinak by prefix `btt_tg1` našel
i tabulky `btt_tg11_…`. Vzor ale dotaz jen zužuje, o tom, jestli tabulka k prefixu patří,
rozhoduje až celý název s platným datem na konci. Datum se čte podle počtu číslic: 8 u TVMS,
14 u VMS.

U MyISAM je `UPDATE_TIME` čas poslední změny datového souboru. U InnoDB, se kterým pracují
cílové servery, je to čas posledního `COMMIT`, který MySQL drží jen v paměti. Po restartu
MySQL je proto NULL, dokud se do tabulky něco nezapíše, a agent ho do té doby hlásí jako
jeden měsíc.

NULL má i právě založená tabulka. Systém ji založí a první data do ní zapíše až o chvíli
později, takže cyklus agenta mezi tím by ohlásil zastavený zápis. Nejnovější tabulce bez
`UPDATE_TIME` se proto první minutu po založení počítá stáří zápisu od `CREATE_TIME`
(UC6-R5). Minuta běží od `CREATE_TIME`, ne od data v názvu: TVMS má v názvu jen den, který
o hodině založení nic neříká.

MySQL 8 navíc `TABLE_ROWS`, `UPDATE_TIME` a další statistiky v `information_schema.TABLES`
nečte pokaždé z úložiště. Vrací je z mezipaměti, kterou obnovuje až po uplynutí
`information_schema_stats_expiry` sekund, ve výchozím stavu jednou denně. Na serverech se to
projevilo tak, že plnící se tabulka surových dat měla v `information_schema` čas zápisu
z chvíle, kdy se na ni agent poprvé zeptal. Workbench po obnovení ukázal čerstvé hodnoty,
agent dál ty staré. Stejně zastarale mohl chodit i počet řádků bufferů. Agent si proto po
každém připojení nastaví `SET SESSION information_schema_stats_expiry = 0` (UC4-R7). Platí
to jen pro jeho připojení, server se nemění. MySQL 5.7 tu proměnnou nezná a mezipaměť nemá,
takže chybu neznámé proměnné agent přejde.

Druhá past je transakce. `mysql-connector-python` má ve výchozím stavu vypnutý autocommit,
takže první dotaz agenta by otevřel transakci, kterou agent nikdy neukončí, protože jen čte.
InnoDB pak v úrovni REPEATABLE READ odpovídá na všechny další dotazy ze snímku pořízeného
na jejím začátku. Na MySQL 8 to platí i pro `information_schema`, jehož tabulky jsou také
InnoDB. Nová tabulka surových dat by pro agenta nevznikla a smazaná by nezmizela, dokud by se
nepřipojil znovu. Na serveru to vypadalo takto: při přepnutí tabulek se hlásil čas zápisu
staré tabulky a u jedné turbíny se počítaly dvě tabulky, přestože nové připojení vidělo
jednu. Agent se proto připojuje s `autocommit=True` (UC4-R8). Na lokální MySQL 5.7 se to
projevit nemohlo: `information_schema` tam transakční není a tabulky jsou MyISAM.
