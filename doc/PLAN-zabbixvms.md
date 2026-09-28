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
- služba a ikona v systray se ověřují ručně (`sc.exe query`, restart serveru, pohled na ikonu)

## Etapy

| # | Název | Hotovo |
| --- | --- | --- |
| 1 | Kostra balíčku a konfigurace | [x] |
| 2 | Katalog metrik a sběr z databáze | [x] |
| 3 | Odesílání a smyčka agenta | [x] |
| 4 | Služba Windows | [x] |
| 5 | Tray aplikace | [x] |
| 6 | Logování a vlastní stav agenta | [x] |
| 7 | Šablona pro Zabbix a návod | [x] |
| 8 | Sledování surových dat | [x] |
| 9 | Doplňování konfigurace | [x] |
| 10 | Aktuální statistiky z information_schema | [x] |
| 11 | Připojení bez otevřené transakce | [x] |
| 12 | Nová tabulka surových dat bez zápisu | [x] |


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

**Doplněno po dokončení etapy:** prodleva mezi cykly se nastavuje v konfiguraci
(`ZabbixConfig.period`, 5 až 120 sekund, výchozí 5), takže UC4-R6 i UC2-R2 mají upravené DoD.
Pozor na `jsonpickle`: ten při načtení nevolá `__init__`, takže konfiguraci zapsané starší
verzí agenta nové pole prostě chybí a její čtení by skončilo `AttributeError`. Řeší to
`Config.fill_missing()`, které chybějícím polím doplní výchozí hodnoty – stejným způsobem se
přidají i pole příští.

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
7. Ručně ověřit: `sc.exe query ZabbixVms` po registraci, start a stop, stav RUNNING po restartu serveru bez přihlášení, ovládání pod účtem bez práv administrátora, běh služby při nedostupné MySQL a konfigurační soubor beze změny po startu a zastavení.

**Stav:** hotovo. Ruční ověření kroku 7 proběhlo, včetně registrace a odebrání služby, takže
UC1-R2, UC1-R3, UC1-R4, UC1-R7 i UC2-R4 přešly na Hotovo.

Dvě věci, na které se při ověřování narazilo a stojí za zapamatování: `sc.exe delete` se ze
správce služeb projeví až po zavření posledního handlu na službu, takže při otevřené konzoli
Služby zůstane služba v mezistavu (`DeleteFlag=1`) a `install` pak selže s chybou 1072. A při
per-user instalaci Pythonu nenastartuje hostitel služby, viz předpoklad níže.

Předpoklad: Python nainstalovaný pro celý stroj, viz [README](../README.md#instalace). Při
instalaci jen pro uživatele služba nenastartuje a `sc.exe start` skončí chybou 1053, protože
hostitel `pythonservice.exe` nenajde `python3XX.dll` na cestě účtu LocalSystem.

Postup ručního ověření, v prostředí s nainstalovaným balíčkem (`pip install .`) a
z příkazové řádky spuštěné jako administrátor. Píše se `sc.exe`, ne `sc` – v PowerShellu
je `sc` alias pro `Set-Content`, takže samotné `sc` správce služeb nespustí:

```
zabbixvms-service install
sc.exe qc ZabbixVms                 # START_TYPE musí být AUTO_START (UC1-R3)
sc.exe sdshow ZabbixVms             # v SDDL přibyl záznam pro BU, tedy BUILTIN\Users (UC1-R7)
sc.exe start ZabbixVms              # -> RUNNING (UC1-R2)
sc.exe stop ZabbixVms               # -> STOPPED
```

Pod účtem **bez** práv administrátora musí `sc.exe query`, `sc.exe start` a `sc.exe stop` projít,
zatímco `sc.exe config ZabbixVms start= disabled` a `sc.exe delete ZabbixVms` musí selhat na
odepřený přístup (UC1-R7). Pro UC1-R3 restartovat server a bez přihlášení ověřit
`sc.exe query ZabbixVms`. Pro UC1-R4 zastavit MySQL a zkontrolovat, že služba zůstává
RUNNING a po nastartování MySQL zase odesílá. Pro UC2-R4 porovnat otisk konfigurace
před startem a po zastavení:

```
Get-FileHash C:\ProgramData\LogicElements\ZabbixVms\config.json
```

Úklid po ověření: `zabbixvms-service remove`.

### Etapa 5 – Tray aplikace
**Účel:** Zobrazit stav služby ikonou v systray a umožnit z ní službu ovládat a otevřít datovou složku.
**Řeší:** UC1-R5, UC1-R6, UC1-R8, UC2-R8
**Kroky:**
1. Vytvořit `servicecontrol.py` s třídou `ServiceController`: zjištění stavu služby a její spuštění, zastavení a restart přes `win32service`.
2. Implementovat v `tray.py` jednobarevnou ikonu přes `Shell_NotifyIcon` z `win32gui`, s názvem agenta v tooltipu.
3. Odvodit barvu ikony ze stavu služby: jedna barva pro RUNNING, odlišná pro stav, kdy služba neběží.
4. Zjišťovat stav služby s periodou 5 sekund a při jeho změně ikonu překreslit.
5. Sestavit kontextové menu s položkami Spustit, Zastavit, Restartovat a Otevřít datovou složku.
6. Otevřít z položky Otevřít datovou složku adresář `data_folder()`, ve kterém leží konfigurace i log.
7. Zaregistrovat při instalaci automatické spuštění tray aplikace po přihlášení uživatele.
8. Napsat testy proti podvrženým objektům: mapování stavu služby na barvu, volání start, stop a restart z položek menu, cesta otevíraná položkou Otevřít datovou složku.
9. Ručně ověřit: ikona v systray po přihlášení, změna barvy do 5 sekund po `sc.exe stop`, všechny tři akce z menu a otevření datové složky bez výzvy UAC.

**Stav:** kroky 1 až 8 jsou hotové, z kroku 9 prošly barvy ikony a tři akce z menu, takže
UC1-R5 a UC1-R6 jsou Hotovo. UC2-R8 je Hotovo až po opravě práv k složce v `ProgramData` (viz etapa 6) – otevřít
konfiguraci šlo hned, ale uložit ji ne. UC1-R8 se ověřil restartem stroje: po něm běžela
služba i tray aplikace, aniž by je kdokoli spouštěl.

Ikona nese uprostřed písmeno Z, aby nebyla jen barevným čtvercem.

Nad rámec PRS má menu ještě položku Ukončit, protože jinak nešla tray aplikace ukončit
jinak než přes Správce úloh. Ptá se na potvrzení s předvybraným Ne, aby ji omylem
netrefil klik ani Enter.

Podle dohody jsou položky menu česky (Spustit, Zastavit, Restartovat, Otevřít datovou složku),
barvy jsou dvě (zelená běží, červená neběží, a to včetně stavu, kdy služba není nainstalovaná)
a automatické spuštění se zapisuje do `HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Run`
pod hodnotou `ZabbixVmsTray` při `zabbixvms-service install`; `remove` ji zase smaže.

Postup ručního ověření:

```
zabbixvms-service install
reg query "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Run" /v ZabbixVmsTray
zabbixvms-tray                  # nebo se odhlásit a znovu přihlásit (UC1-R8)
sc.exe stop ZabbixVms           # ikona zčervená do 5 s (UC1-R5)
sc.exe start ZabbixVms          # ikona zezelená do 5 s
```

Z kontextového menu ikony vyzkoušet Spustit, Zastavit a Restartovat a výsledek ověřit
příkazem `sc.exe query ZabbixVms` (UC1-R6); položka Otevřít datovou složku musí otevřít
`C:\ProgramData\LogicElements\ZabbixVms` s konfigurací i logem uvnitř a nesmí vyvolat
výzvu UAC (UC2-R8). Pro UC1-R8 restartovat server a po přihlášení
zkontrolovat, že ikona je v systray. Po `zabbixvms-service remove` už hodnota
`ZabbixVmsTray` v registru být nesmí.

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

**Stav:** kroky 1 až 7 jsou hotové. Krok 8 proběhl: start i zastavení služby se v Prohlížeči
událostí objevily pod zdrojem `ZabbixVms`, takže UC5-R2 je Hotovo.

**Hotovo, ale se dvěma zádrhely, které stojí za zapamatování:**

- Zápis do jednoho logu ze dvou procesů nestačí ošetřit jen souběžností. Nejdřív se ukázalo,
  že režim append na Windows není atomický (ztratilo se 6 z 60 záznamů), což řeší zámek na
  první bajt souboru. Pak se ukázalo, že tray do logu nesmí vůbec, protože soubor zakládá
  služba pod LocalSystem a `Users` na něm měli jen čtení – `PermissionError` se navíc nikde
  neobjevil, protože tray běží bez konzole. Řeší to `grant_users_data_folder()`, které při
  registraci dá `BUILTIN\Users` na složku v `ProgramData` právo Modify s děděním. Totéž
  odblokovalo ukládání konfigurace (UC2-R8).
- Testy zapisovaly do skutečného Windows Event Logu, než to zachytil `tests/conftest.py`.

Dvě rozhodnutí, která při implementaci padla:

- **Souběžný zápis do jednoho logu.** Otevřít soubor v režimu append nestačí – běhové
  prostředí C ve Windows append emuluje seekem na konec a zápisem, takže si dva procesy
  záznamy přepisují. Ověřeno: ze 60 záznamů se jich ztratilo 6. Každý záznam se proto
  zapisuje pod výhradním zámkem na první bajt souboru (`msvcrt.locking`). Po opravě prošel
  zátěžový test se čtyřmi procesy a 1200 záznamy bez jediné ztráty.
- **Zdroj varování (stav 1).** DoD popisuje stav 1 jako varování, po kterém agent pokračuje,
  ale neříká, co ho vyvolá. Použil se případ, kdy turbína má v konfiguraci bufferovou
  tabulku, která v databázi není: agent počítá dál, ale nula řádků by vypadala jako prázdný
  buffer, což je něco úplně jiného než chybějící tabulka.

Ruční ověření: po `zabbixvms-service install` spustit a zastavit službu a v Prohlížeči
událostí (Windows Logs → Application) najít události zdroje `ZabbixVms`. Log soubor je
v `C:\ProgramData\LogicElements\ZabbixVms\zabbixvms.log`.

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

**Stav:** hotovo. Šablona se do Zabbixu 7 naimportovala bez ruční úpravy souboru, takže
UC3-R4 i UC5-R4 jsou Hotovo.

Import napoprvé neprošel a stálo to tři kola. Co z toho platí i pro příští úpravy šablony:

- **Triggery nemají v exportu vlastní sekci pod šablonou.** Každý sedí uvnitř položky, na
  kterou se jeho výraz odkazuje (`Invalid tag ... unexpected tag "triggers"`).
- **Uuid musí být verze 4.** Odvozování přes `uuid5`, které drží hodnoty stabilní mezi
  generováními, dává verzi 5 a Zabbix ho odmítne (`Invalid parameter "/1/uuid": UUIDv4 is
  expected`). Řeší se přepsáním bitů verze a varianty, hodnota zůstává deterministická.
- **Sekce skupin se od Zabbixu 6.4 jmenuje `template_groups`**, ne `groups`.

Struktura exportu se z kódu ověřit nedá, rozhodčím je až import na serveru. Testy proto
drží alespoň to, co už víme: tvar uuid, umístění triggerů i název sekce skupin.

**Doplněno po dokončení etapy:** triggery se stejně jako metriky vedou jako tabulka v PRS
a katalog `TRIGGERS` v `metrics.py` je jejím zrcadlem; test tabulku z PRS parsuje a porovnává,
takže se nemohou rozejít. Přidání dalšího triggeru je tak řádek v tabulce, řádek v katalogu
a reimport šablony, bez zásahu do generátoru. Sloupec s klíčem metriky zároveň určuje, pod
kterou položkou trigger v exportu leží.

Export je ve formátu **Zabbix 7.0**, tedy ve verzi serveru, do kterého se importuje. Na jiný
formát se přejde změnou `EXPORT_VERSION` v `template.py` a přegenerováním souboru; pozor, že
samotná verze nestačí – Zabbix v 6.4 přejmenoval sekci `groups` na `template_groups`, což
řeší `groups_section()`. Uuid objektů se odvozují z pevného jmenného prostoru, takže jsou při
každém generování stejné a opakovaný import šablonu aktualizuje místo zakládání druhé.

Ověření: naimportovat `src/zabbixvms/data/zabbix_template.yaml` podle
[návodu](NAVOD-zabbix.md) a zkontrolovat, že u hosta vzniklo dvanáct položek typu Zabbix
trapper, value map u `vms.agent_status` a tři triggery.

### Etapa 8 – Sledování surových dat
**Účel:** Hlásit do Zabbixu, že se surová data VMS a TVMS přestala zapisovat nebo exportovat.
**Řeší:** UC6-R1, UC6-R2, UC6-R3, UC6-R4
**Kroky:**
1. Přidat do `Turbine` pole `raw_prefixes` (výchozí prázdný seznam), v `Turbine.validate()` odmítnout prefix mimo `[A-Za-z0-9_]+` a v `Config.fill_missing()` doplnit prázdný seznam turbínám z konfigurace bez tohoto pole.
2. Doplnit `"raw_prefixes": []` do `data/config_default.json`.
3. Implementovat v `collector.py` přiřazení tabulky k prefixu podle celého názvu `<prefix>_yyyymmdd` nebo `<prefix>_yyyymmddHHMMSS` s platným datem.
4. Implementovat dotaz na `TABLE_NAME` a `UPDATE_TIME` z `information_schema.TABLES` s escapovaným vzorem LIKE pro všechny prefixy turbíny jedním dotazem; turbína bez prefixů se neptá.
5. Implementovat výpočet `vms.raw_tables` (největší počet tabulek jednoho prefixu) a `vms.raw_write_age` (největší stáří `UPDATE_TIME` nejnovější tabulky prefixu, bez tabulky nebo bez `UPDATE_TIME` jeden měsíc), u turbíny bez prefixů 0.
6. Přidat obě metriky a oba triggery z PRS do katalogů v `metrics.py` a přegenerovat `data/zabbix_template.yaml`.
7. Napsat testy konfigurace: výchozí prázdný seznam, uložení a načtení, načtení konfigurace bez pole, odmítnutí neplatného prefixu, pole ve výchozí konfiguraci.
8. Napsat testy collectoru proti podvrženým objektům: přiřazení tabulek včetně prefixů, které jiným jen začínají, a neplatných dat, maximum počtu přes prefixy, stáří zápisu z nejnovější tabulky a nejhoršího prefixu, jeden měsíc bez tabulky a bez `UPDATE_TIME`, nuly a žádný dotaz bez prefixů, escapování vzoru a nastavená databáze.
9. Napsat test proti testovací databázi: prefix, který v databázi není, vrátí prázdný seznam.
10. Upravit test závislostí triggerů na klidu turbíny o `vms.raw_write_age`.
11. Doplnit dokumentaci: `NAVRH-zabbixvms.md`, `NAVOD-zabbix.md` (nastavení prefixů, závislost na klidu), `CHYBY-agenta.md` a úvod `README.md`.
12. Zvýšit verzi balíčku na 0.2.0.
13. Ručně ověřit import šablony do Zabbixu: dvě nové položky, dva triggery a závislost triggeru na zápis na triggeru Turbína pod nominálními otáčkami.

**Stav:** hotovo. Testy prošly včetně databázových proti lokální `BVMS` (MySQL 5.7.17),
takže UC6-R1 až UC6-R4 jsou Hotovo. Ruční krok 13 prošel: šablona se do Zabbixu
naimportovala a trigger na zápis surových dat je závislý na triggeru Turbína pod
nominálními otáčkami. Šablona přibrala jen nové položky a triggery, stávající objekty
i jejich uuid se nezměnily.

Proti skutečným tabulkám surových dat se agent ověřil na serveru s VMS i TVMS (turbíny TG11
a TG12, každá s prefixem `btt_tgXY` a `tgXY_out`). Do Zabbixu tam chodí `vms.raw_tables` = 1
a `vms.raw_write_age` = 1 s, tedy jedna tabulka na prefix a průběžný zápis.

Co stojí za zapamatování: `python -m zabbixvms.template` zapisuje šablonu vedle toho balíčku,
který Python importuje. Ve `.venv` s běžnou (ne editovatelnou) instalací je to kopie
v `site-packages`, ne soubor v `src`, takže se přegenerovává s `PYTHONPATH=src`. Hlídá to test
`test_the_file_in_the_package_is_what_the_generator_builds`, který selže, když zůstane
soubor v `src` starý.

### Etapa 9 – Doplňování konfigurace
**Účel:** Doplňovat do konfigurace jen položky z novějších verzí a při aktualizaci je zapsat do souboru.
**Řeší:** UC2-R7, UC2-R9, UC2-R10
**Kroky:**
1. Nahradit podmínky v `Config.fill_missing()` tabulkou `ADDED_FIELDS` v `config.py` s poli přidanými po první verzi (`ZabbixConfig.period`, `Turbine.raw_prefixes`) a jejich výchozími hodnotami; `fill_missing()` vrací seznam doplněných položek.
2. Při načtení konfigurace odmítnout soubor, ve kterém chybí jiná položka než z `ADDED_FIELDS`, s `ConfigError`, který chybějící položky vyjmenuje.
3. Přidat do `config.py` funkci `complete_config()`: načte konfiguraci bez doplnění, doplní položky z `ADDED_FIELDS`, ověří platnost, uloží zálohu `config.json.bak` a nový soubor zapíše přes dočasný soubor; když nic nechybí nebo soubor neexistuje, nic nezmění.
4. Přidat do `zabbixvms-service` příkaz `complete-config`, který zavolá `complete_config()`, vypíše doplněné položky a u neplatné konfigurace skončí nenulovým kódem.
5. Volat v `install.ps1` po výměně balíčku a před spuštěním služby `zabbixvms-service complete-config`, pokud konfigurace existuje; neúspěch jen ohlásit.
6. Napsat testy: odmítnutí konfigurace bez `system_id`, `location` a celé skupiny, seznam doplněných položek, zápis chybějících položek se zachováním ostatních hodnot, záloha s původním obsahem, beze změny u úplné, chybějící a neplatné konfigurace, příkaz `complete-config` a jeho návratový kód.
7. Doplnit dokumentaci: `README.md`, `BUILD-balicku.md` (aktualizace), `CHYBY-agenta.md` (chybějící položka), `NAVRH-zabbixvms.md`.
8. Zvýšit verzi balíčku na 0.2.1.
9. Ručně ověřit aktualizaci přes `install.ps1` na stroji s konfigurací starší verze: nové položky v `config.json`, záloha `config.json.bak`, služba běží.

**Stav:** kroky 1 až 8 jsou hotové a testy prošly, takže UC2-R9 je Hotovo. UC2-R7 měl
upřesněné DoD o výjimku pro instalační skript, a protože se tím jeho stávající testy
nezměnily, je zase Hotovo. Ruční krok 9 prošel: aktualizace přes `install.ps1` doplnila
do konfigurace starší verze nová pole a nechala vedle `config.json.bak`, takže UC2-R10 je
Hotovo. Python část drží testy, samotný `install.ps1` jen to ruční ověření.
Příkaz `complete-config` se vyzkoušel na souboru ve tvaru z verze 0.1.x v dočasné
složce: doplnil `period` a oba `raw_prefixes` a druhý běh už nic nezměnil.

Chyba při čtení poškozeného souboru dřív prošla ven jako výjimka jsonpickle. Knihovna
zkouší postupně všechny načtené backendy a vyhodí chybu toho posledního, takže u rozbitého
JSON přišla chyba parseru YAML. Teď z ní vzniká `ConfigError` s textem
`cannot read configuration`, jak ho popisuje `CHYBY-agenta.md`.

### Etapa 10 – Aktuální statistiky z information_schema
**Účel:** Číst `TABLE_ROWS` a `UPDATE_TIME` na MySQL 8 aktuální, ne z mezipaměti obnovované jednou denně.
**Řeší:** UC4-R7
**Kroky:**
1. Nastavit v `Collector.connect()` hned po připojení `SET SESSION information_schema_stats_expiry = 0`; chybu `ER_UNKNOWN_SYSTEM_VARIABLE` serveru bez této proměnné přejít, jinou chybu nechat projít.
2. Upravit `FakeConnection` v testech collectoru, aby příkazy `SET` zaznamenávala zvlášť a uměla na ně odpovědět chybou.
3. Napsat testy: nastavení po připojení, nastavení znovu po novém připojení, přechod přes neznámou proměnnou, propuštění jiné chyby.
4. Doplnit `NAVRH-zabbixvms.md` o mezipaměť statistik MySQL 8.
5. Zvýšit verzi balíčku na 0.2.2.
6. Ručně ověřit na serveru s MySQL 8: `vms.raw_write_age` drží malé hodnoty i při přepnutí tabulek a odpovídá `UPDATE_TIME`, který ukazuje Workbench po obnovení.

**Stav:** hotovo. Testy prošly a databázové testy proti lokální MySQL 5.7 ověřily, že agent
chybu neznámé proměnné přejde. Ruční krok 6 prošel: na serverech s MySQL 8 chodí stáří
zápisu aktuální i přes přepnutí tabulek, takže UC4-R7 je Hotovo.

Na tuhle příčinu se přišlo oklikou. Nejdřív to vypadalo, že agent při přepnutí tabulek
vybírá tu starou, pak na commit nové tabulky zdržený exportem. Rozhodl až údaj, že i na
dalších serverech se tabulka plní, `UPDATE_TIME` přitom stojí a po obnovení ve Workbenchi
je čerstvý. Pozor tedy u každé hodnoty ze statistik `information_schema` na MySQL 8:
bez tohoto nastavení je až den stará.

### Etapa 11 – Připojení bez otevřené transakce
**Účel:** Aby agent při dlouhém běhu na jednom připojení neviděl databázi ve stavu, v jakém byla při jeho prvním dotazu.
**Řeší:** UC4-R8
**Kroky:**
1. Připojovat se v `Collector.connect()` s `autocommit=True`.
2. Doplnit test parametrů připojení a test, že připojení běží v režimu autocommit.
3. Napsat test proti testovací databázi, že `@@autocommit` připojení agenta je 1.
4. Doplnit `NAVRH-zabbixvms.md` o snímek transakce v InnoDB a v `information_schema` MySQL 8.
5. Zvýšit verzi balíčku na 0.2.3.
6. Ručně ověřit na serveru s MySQL 8: po přepnutí tabulek surových dat a po smazání staré tabulky hlásí agent bez restartu služby správný počet tabulek i stáří zápisu.

**Stav:** hotovo. Testy prošly. Příčinu potvrdil server: služba na připojení otevřeném od
svého startu hlásila u TG42 dvě tabulky surových dat, nové připojení vidělo jednu a po
restartu služby hlásila jednu i ona. Ruční krok 6 prošel: agent přečkal přepnutí tabulek
i smazání staré tabulky bez restartu služby a hlásil správný počet tabulek i stáří zápisu,
takže UC4-R8 je Hotovo.

### Etapa 12 – Nová tabulka surových dat bez zápisu
**Účel:** Nehlásit chybu zápisu ve chvíli, kdy systém novou tabulku surových dat založil, ale ještě do ní nezapsal.
**Řeší:** UC6-R4, UC6-R5
**Kroky:**
1. Číst v dotazu na tabulky surových dat i `CREATE_TIME` a držet ho v `RawTable`.
2. Počítat stáří zápisu nejnovější tabulky bez `UPDATE_TIME` od `CREATE_TIME`, dokud od něj neuplynula minuta (`FRESH_RAW_TABLE`).
3. Doplnit `FakeConnection` v testech collectoru o `CREATE_TIME`.
4. Napsat testy: tabulka bez zápisu mladší než minuta, tabulka právě minutu stará, mladá tabulka se zápisem, minuta od `CREATE_TIME` a ne od data v názvu, tabulka bez `CREATE_TIME`.
5. Doplnit `NAVRH-zabbixvms.md` a `NAVOD-zabbix.md`.
6. Zvýšit verzi balíčku na 0.2.4.
7. Ručně ověřit na serveru: při přepnutí tabulek surových dat se neozve Chyba zápisu surových dat.

**Stav:** hotovo. Testy prošly, takže UC6-R4 i UC6-R5 jsou Hotovo; UC6-R4 se kvůli úpravě
DoD vracel na Zbývá. Proti lokální MySQL 5.7 se potvrdilo, že právě založená InnoDB tabulka
má `UPDATE_TIME` NULL a `CREATE_TIME` vyplněný: dřív z toho bylo stáří zápisu jeden měsíc,
teď 0 s. Ruční krok 7 prošel: první přepnutí tabulek surových dat s verzí 0.2.4 se na
serveru obešlo bez Chyby zápisu surových dat.
