# Plán – zabbixvms

## Typ výstupu

- zdrojový kód – balíček `zabbixvms` se službou a tray aplikací
- testy – `pytest`
- konfigurace – šablona pro Zabbix ve formátu YAML
- dokumentace – návod k nastavení Zabbixu

## Prostředí a nástroje

- Python 3.12 a novější, pouze Windows
- setuptools, zdroje v `src/`, struktura modulů podle [návrhu](NAVRH-zabbixvms.md)
- závislosti: `mysql-connector-python`, `jsonpickle`, `zabbix_utils`, `pywin32`, `PyYAML`
- testy: `pytest`; výpočty a konfigurace proti podvrženým objektům, databázové dotazy proti testovací databázi `BVMS`
- služba a ikona v systray se ověřují ručně (`sc query`, restart serveru, pohled na ikonu)

## Etapy

| # | Název | Hotovo |
| --- | --- | --- |
| 1 | Kostra balíčku a konfigurace | [ ] |
| 2 | Katalog metrik a sběr z databáze | [ ] |
| 3 | Odesílání a smyčka agenta | [ ] |
| 4 | Služba Windows | [ ] |
| 5 | Tray aplikace | [ ] |
| 6 | Logování a vlastní stav agenta | [ ] |
| 7 | Šablona pro Zabbix a návod | [ ] |

Kroky jsou rozepsané pro etapy 1 až 3; u etap 4 až 7 se doplní, až na ně přijde řada.

### Etapa 1 – Kostra balíčku a konfigurace
**Účel:** Založit strukturu balíčku a zprovoznit konfiguraci v `ProgramData`.
**Řeší:** UC1-R1, UC2-R1, UC2-R3, UC2-R4, UC2-R6, UC2-R7
**Kroky:**
1. Přejmenovat `src/zabagent` na `src/zabbixvms` a odstranit moduly `ZabAgent.py`, `ZabConfig.py`, `ZabSender.py`.
2. Upravit v `pyproject.toml` `package-data` na `zabbixvms` a doplnit `data/*.yaml`; přidat `pytest` jako vývojovou závislost.
3. Vytvořit `service.py` a `tray.py` s prázdnou funkcí `main()` a deklarovat vstupní body `zabbixvms-service` a `zabbixvms-tray`.
4. Vytvořit `config.py` s třídami `Config`, `ZabbixConfig`, `DatabaseConfig` a `Turbine`.
5. Implementovat uložení a načtení konfigurace přes `jsonpickle`.
6. Implementovat cestu `C:\ProgramData\LogicElements\ZabbixVms\config.json` a nasazení výchozí konfigurace z `data/config_default.json`, pokud soubor ještě neexistuje.
7. Implementovat kontrolu rozsahů: 1 až 4 turbíny, 0 až 2 buffery u turbíny.
8. Napsat testy: uložení a načtení konfigurace se shodnými hodnotami, nasazení výchozí konfigurace do prázdné složky, ponechání existujícího souboru beze změny, odmítnutí konfigurace mimo povolené rozsahy.

### Etapa 2 – Katalog metrik a sběr z databáze
**Účel:** Definovat sadu metrik a naplnit ji hodnotami z databáze `BVMS`.
**Řeší:** UC3-R1, UC3-R2, UC3-R3, UC4-R1, UC4-R2, UC4-R3, UC4-R4, UC4-R5
**Kroky:**
1. Vytvořit `metrics.py` s třídou `Metric`, výčtem `ValueType` a katalogem `METRICS` podle tabulky metrik v PRS.
2. Vytvořit `collector.py` s třídou `Collector` a připojením k MySQL přes `mysql-connector-python`.
3. Implementovat dotaz na řádek informační tabulky podle `SystemId` s vyjmenovanými sloupci.
4. Implementovat dotaz na počty řádků bufferových tabulek z `information_schema.TABLES`.
5. Implementovat výpočty hodnot podle tabulky zdrojů v PRS, včetně hodnoty -1 při stáří nad 1825 dní.
6. Implementovat nulové hodnoty metrik u bufferu, který turbína nemá nastavený.
7. Napsat testy proti podvrženým objektům: výpočet otáček, výpočet stáří, mez -1, nuly u nenastaveného bufferu, shoda odeslaných klíčů s katalogem `METRICS`.
8. Napsat testy proti testovací databázi: přečtení řádku podle `SystemId`, přečtení počtů řádků bufferů, nezávislost hodnot na pořadí sloupců informační tabulky.

### Etapa 3 – Odesílání a smyčka agenta
**Účel:** Odeslat spočítané hodnoty do Zabbixu a rozběhnout opakovaný cyklus.
**Řeší:** UC1-R4, UC2-R2, UC2-R5, UC4-R6
**Kroky:**
1. Vytvořit `sender.py` s třídou `TrapperSender` nad knihovnou `zabbix_utils`.
2. Skládat název hostu jako `<location>_<název turbíny>`.
3. Vyhodnotit `failed` v odpovědi trapperu a odmítnuté hodnoty ohlásit jako chybu.
4. Vytvořit `agent.py` s třídou `Agent`: cyklus přes turbíny z konfigurace, odeslání hodnot, prodleva 5 sekund.
5. Ošetřit výjimky jednoho cyklu tak, aby smyčka pokračovala dalším cyklem.
6. Napsat testy proti podvrženým objektům: složení názvu hostu, odeslání na adresu a port z konfigurace, pokračování smyčky po výjimce v cyklu, prodleva mezi cykly.

### Etapa 4 – Služba Windows
**Účel:** Zaregistrovat agenta jako službu, která startuje se systémem a jde ovládat i bez práv administrátora.
**Řeší:** UC1-R2, UC1-R3, UC1-R7

### Etapa 5 – Tray aplikace
**Účel:** Zobrazit stav služby ikonou v systray a umožnit z ní službu ovládat a otevřít konfiguraci.
**Řeší:** UC1-R5, UC1-R6, UC1-R8, UC2-R8

### Etapa 6 – Logování a vlastní stav agenta
**Účel:** Zaznamenat chyby do logu a Event Logu a odeslat stav agenta do Zabbixu.
**Řeší:** UC5-R1, UC5-R2, UC5-R3

### Etapa 7 – Šablona pro Zabbix a návod
**Účel:** Vygenerovat šablonu z katalogu metrik a popsat její nasazení.
**Řeší:** UC3-R4, UC5-R4
