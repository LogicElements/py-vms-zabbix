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
| 1 | Kostra balíčku a konfigurace | [x] |
| 2 | Katalog metrik a sběr z databáze | [x] |
| 3 | Odesílání a smyčka agenta | [x] |
| 4 | Služba Windows | [ ] |
| 5 | Tray aplikace | [ ] |
| 6 | Logování a vlastní stav agenta | [ ] |
| 7 | Šablona pro Zabbix a návod | [ ] |


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

**Poznámka k dokončení:** UC2-R6 přešel na Hotovo až v etapě 2, kdy se z nastavené databáze
opravdu čte. UC2-R4 zůstává ve stavu Zbývá – jeho kód je hotový (agent konfiguraci
nepřepisuje), ale DoD se ověří až proti běžící službě v etapě 4.

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

**Poznámka k dokončení:** databázové testy jsou označené značkou `db` a když databáze `BVMS`
není dostupná, přeskočí se (`pytest -m db` je spustí samostatně). Metriky `vms.agent_status`
a `vms.agent_error` collector neplní, pocházejí z vlastního stavu agenta (etapa 6).

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

**Poznámka k dokončení:** UC1-R4 zůstává ve stavu Zbývá – smyčka chybu cyklu přežije a je to
otestované, ale DoD mluví o stavu služby RUNNING, což jde ověřit až v etapě 4. Po chybě cyklu
se zahodí databázové spojení, takže další cyklus navazuje na čerstvé. Odeslání na živý Zabbix
se neověřovalo, aby do něj nešla testovací data.

### Etapa 4 – Služba Windows
**Účel:** Zaregistrovat agenta jako službu, která startuje se systémem a jde ovládat i bez práv administrátora.
**Řeší:** UC1-R2, UC1-R3, UC1-R4, UC1-R7, UC2-R4
**Kroky:**
1. Implementovat v `service.py` třídu `ZabbixVmsService` nad `win32serviceutil.ServiceFramework` s názvem `ZabbixVms`, zobrazovaným názvem „VMS zabbix agent" a popisem služby.
2. Načíst v `SvcDoRun` konfiguraci přes `load_config()` a spustit `Agent.run()`; v `SvcStop` zavolat `Agent.stop()` a ohlásit SCM zastavení.
3. Rozšířit `main()` o příkazy pro registraci a odregistraci služby přes `win32serviceutil.HandleCommandLine`.
4. Nastavit při registraci typ spuštění na Automatic.
5. Nastavit při registraci deskriptor zabezpečení služby tak, aby uživatelé bez práv administrátora směli službu dotazovat, spouštět a zastavovat, ne však měnit její konfiguraci ani ji odregistrovat.
6. Napsat testy proti podvrženému agentovi: `SvcDoRun` spustí smyčku, `SvcStop` ji ukončí, sestavení deskriptoru zabezpečení z požadovaných práv.
7. Ručně ověřit: `sc query ZabbixVms` po registraci, start a stop, stav RUNNING po restartu serveru bez přihlášení, ovládání pod účtem bez práv administrátora, běh služby při nedostupné MySQL a konfigurační soubor beze změny po startu a zastavení.

### Etapa 5 – Tray aplikace
**Účel:** Zobrazit stav služby ikonou v systray a umožnit z ní službu ovládat a otevřít konfiguraci.
**Řeší:** UC1-R5, UC1-R6, UC1-R8, UC2-R8
**Kroky:**
1. Vytvořit `servicecontrol.py` s třídou `ServiceController`: zjištění stavu služby a její spuštění, zastavení a restart přes `win32service`.
2. Implementovat v `tray.py` jednobarevnou ikonu přes `Shell_NotifyIcon` z `win32gui`, s názvem agenta v tooltipu.
3. Odvodit barvu ikony ze stavu služby: jedna barva pro RUNNING, odlišná pro stav, kdy služba neběží.
4. Zjišťovat stav služby s periodou 5 sekund a při jeho změně ikonu překreslit.
5. Sestavit kontextové menu s položkami Spustit, Zastavit, Restartovat a Open configuration.
6. Otevřít z položky Open configuration soubor `config_path()` v editoru přiřazeném systémem.
7. Zaregistrovat při instalaci automatické spuštění tray aplikace po přihlášení uživatele.
8. Napsat testy proti podvrženým objektům: mapování stavu služby na barvu, volání start, stop a restart z položek menu, cesta otevíraná položkou Open configuration.
9. Ručně ověřit: ikona v systray po přihlášení, změna barvy do 5 sekund po `sc stop`, všechny tři akce z menu a otevření konfigurace bez výzvy UAC.

### Etapa 6 – Logování a vlastní stav agenta
**Účel:** Zaznamenat chyby do logu a Event Logu a odeslat stav agenta do Zabbixu.
**Řeší:** UC5-R1, UC5-R2, UC5-R3
**Kroky:**
1. Nastavit logování do souboru ve složce `config_path().parent` přes `RotatingFileHandler`, 1 MB na soubor a 5 uchovaných souborů, se záznamem ve tvaru časová značka, úroveň a text.
2. Zapisovat do logu start a zastavení služby, neplatnou konfiguraci, nedostupnost MySQL i Zabbixu a hodnoty odmítnuté Zabbixem.
3. Umožnit zápis do téhož logu službě i tray aplikaci současně.
4. Zapisovat start, zastavení a chyby bránící běhu do Windows Event Logu pod zdrojem `ZabbixVms`.
5. Odvodit v `Agent` stav: 0 po cyklu bez chyby, 1 při varování, po kterém cyklus pokračuje, 2 při chybě bránící získat nebo odeslat hodnoty.
6. Odesílat v každém cyklu `vms.agent_status` a `vms.agent_error` na host každé turbíny, s textem zkráceným na 255 znaků.
7. Napsat testy proti podvrženým objektům: rotace logu po dosažení velikosti, stav 0, 1 a 2 podle průběhu cyklu, prázdný `vms.agent_error` při stavu 0, zkrácení textu na 255 znaků, odeslání obou metrik na každý host.
8. Ručně ověřit záznam startu a zastavení služby v Event Vieweru.

### Etapa 7 – Šablona pro Zabbix a návod
**Účel:** Vygenerovat šablonu z katalogu metrik a popsat její nasazení.
**Řeší:** UC3-R4, UC5-R4
**Kroky:**
1. Vytvořit `template.py`, který z katalogu `METRICS` sestaví šablonu ve formátu YAML; každá metrika je položka typu Zabbix trapper s klíčem, názvem, typem hodnoty a jednotkou z katalogu.
2. Doplnit do šablony value map překládající hodnoty 0, 1 a 2 metriky `vms.agent_status` na text.
3. Doplnit do šablony tři triggery: `vms.agent_status` větší než 0, neprázdný `vms.agent_error` s textem chyby ve jméně triggeru, a nedoručení žádné hodnoty po dobu 5 minut.
4. Vygenerovat `src/zabbixvms/data/zabbix_template.yaml` a zahrnout ho do balíčku.
5. Napsat testy: klíče položek šablony odpovídají `METRICS` bez přebytků a bez chybějících, každá položka je typu trapper a má typ hodnoty i jednotku podle katalogu, šablona je platný YAML s value map a třemi triggery.
6. Sepsat `doc/NAVOD-zabbix.md` se třemi kroky: založení hostu `<location>_<název turbíny>`, import šablony z balíčku a přiřazení šablony hostu.
7. Doplnit odkaz na návod do rozcestníku v `README.md`.
