# Product Requirement Specification (PRS)

## Přehled requirementů

| Requirement | Popis | Stav | Test |
| --- | --- | --- | --- |
| UC1-R1 | Implementace v Pythonu, jeden balíček se službou i tray aplikací | Hotovo | tests/test_entrypoints.py |
| UC1-R2 | Registrace a ovládání jako služba Windows `ZabbixVms` | Hotovo | tests/test_service.py |
| UC1-R3 | Automatický start se systémem bez přihlášení uživatele | Hotovo | N/A |
| UC1-R4 | Nepřetržitý běh, chyba jednoho cyklu službu neukončí | Hotovo | tests/test_agent.py |
| UC1-R5 | Ikona v systray signalizující barvou stav služby | Hotovo | tests/test_tray.py |
| UC1-R6 | Spuštění, zastavení a restart služby z kontextového menu ikony | Hotovo | tests/test_tray.py |
| UC1-R7 | Ovládání služby i běžným uživatelem, povolené přes ACL služby | Hotovo | tests/test_service.py |
| UC1-R8 | Automatické spuštění tray aplikace při přihlášení uživatele | Zbývá | |
| UC2-R1 | Konfigurace jako JSON dump konfigurační třídy přes jsonpickle | Hotovo | tests/test_config.py |
| UC2-R2 | Skupina parametrů odesílání do Zabbixu: spojení, `location` a prodleva | Hotovo | tests/test_sender.py |
| UC2-R3 | Seznam 1 až 4 turbín, každá nastavená samostatně | Hotovo | tests/test_config.py |
| UC2-R4 | Agent konfiguraci při svém běhu nepřepisuje | Hotovo | tests/test_config.py |
| UC2-R5 | Turbína popsaná názvem, system_id a nejvýše dvěma buffery | Hotovo | tests/test_sender.py |
| UC2-R6 | Skupina parametrů databáze MySQL: spojení a tabulka `info` | Hotovo | tests/test_collector.py |
| UC2-R7 | Aktivní konfigurace v ProgramData, v balíčku jen výchozí šablona | Hotovo | tests/test_config.py |
| UC2-R8 | Otevření konfigurace k editaci z kontextového menu ikony | Hotovo | tests/test_tray.py |
| UC3-R1 | Sada odesílaných metrik vedená jako tabulka v PRS | Hotovo | tests/test_metrics.py |
| UC3-R2 | Sloupce tabulky dostačují k založení položky v Zabbixu | Hotovo | tests/test_metrics.py |
| UC3-R3 | Metriky bufferů podle počtu nastavených bufferů turbíny | Hotovo | tests/test_collector.py |
| UC3-R4 | Šablona pro Zabbix v balíčku a stručný návod k jejímu nasazení v `doc/` | Hotovo | tests/test_template.py |
| UC4-R1 | Zdroje hodnot metrik popsané tabulkou | Hotovo | tests/test_collector.py |
| UC4-R2 | Řádek `info` čtený pro každou turbínu podle jejího `system_id` | Hotovo | tests/test_collector_db.py |
| UC4-R3 | Čtení sloupců `info` podle názvu, ne podle pozice | Hotovo | tests/test_collector_db.py |
| UC4-R4 | Stáří v celých sekundách proti času měření, saturované na jeden měsíc | Hotovo | tests/test_collector.py |
| UC4-R5 | Buffery: stáří a bulk z pevných pozic, počet řádků podle názvu tabulky | Hotovo | tests/test_collector.py |
| UC4-R6 | Prodleva mezi cykly měření nastavitelná v rozsahu 5 až 120 sekund | Hotovo | tests/test_agent.py |
| UC5-R1 | Logovací soubor s provozními událostmi a chybami | Hotovo | tests/test_log.py |
| UC5-R2 | Start, zastavení a zásadní chyby ve Windows Event Logu | Hotovo | N/A |
| UC5-R3 | Vlastní stav agenta odesílaný do Zabbixu jako dvojice metrik | Hotovo | tests/test_agent.py |
| UC5-R4 | Value map a triggery pro hlášení chyb v šabloně | Hotovo | tests/test_template.py |

## Účel projektu

Na turbíně běží sada na sebe navazujících aplikací VMS: sběr dat z VMS elektroniky, výpočet
vibrací z nasbíraných dat a přenos vypočítaných hodnot na server TLCS. Když kterákoli z nich
přestane běžet nebo se dostane do nestandardního stavu, přenos dat se zastaví nebo začnou
chybět hodnoty.

Agent proto vystavuje stav těchto aplikací a stav turbíny v Zabbixu, kde už je zavedený dohled
a alerting. Přínosem je včasný report o výpadku běhu softwaru nebo o nestandardním stavu, aby
se dal řešit hned.

## UC1 – Nepřetržitý provoz agenta na serveru

Aktérem je obsluha serveru VMS. Cílem je mít dohledového agenta trvale v provozu bez ruční
péče a mít po ruce jeho ovládání. Spouštěčem je nasazení agenta na server a dále každý start
serveru. Agent je na serveru zaregistrovaný jako služba, startuje se systémem a běží
nepřetržitě; v systray přihlášeného uživatele je jeho ikona, která barvou signalizuje stav
služby a z jejíhož kontextového menu jde služba spustit, zastavit a restartovat, aniž by k tomu
byla potřeba oprávnění administrátora.

### UC1-R1
**Popis:** Agent je implementovaný v Pythonu a nasaditelný na Windows serveru, na kterém běží VMS.
**DoD:**
- Balíček se nainstaluje příkazem `pip install .` na Windows serveru s Pythonem 3.12 nebo novějším.
- Instalace nevyžaduje jiné běhové prostředí než Python a závislosti deklarované v `pyproject.toml`.
- Jedna instalace přinese službu i tray aplikaci; každá má vlastní vstupní bod.
- Vstupní bod tray aplikace se spustí bez konzolového okna.

### UC1-R2
**Popis:** Agent se na serveru zaregistruje jako služba Windows a dá se ovládat standardními prostředky systému.
**DoD:**
- Existuje příkaz, který službu zaregistruje, a příkaz, který ji odregistruje.
- Po registraci je služba uvedená v `services.msc` pod názvem `ZabbixVms` se zobrazovaným názvem „VMS zabbix agent".
- `sc query ZabbixVms` vrací stav služby, `sc start ZabbixVms` ji převede do stavu RUNNING a `sc stop ZabbixVms` do stavu STOPPED.
- Po odregistrování už služba v `services.msc` uvedená není.

### UC1-R3
**Popis:** Služba se spouští automaticky při startu serveru, bez přihlášení uživatele.
**DoD:**
- Typ spuštění služby je Automatic.
- Po restartu serveru je služba ve stavu RUNNING, aniž se na server kdokoli přihlásil.

### UC1-R4
**Popis:** Služba běží nepřetržitě – chyba v jednom cyklu měření ji neukončí.
**DoD:**
- Při nedostupném zdroji dat (MySQL) nebo nedostupném cíli (Zabbix) zůstane služba ve stavu RUNNING.
- Po obnovení dostupnosti pokračuje v odesílání metrik bez ručního zásahu.

### UC1-R5
**Popis:** Ikona agenta v systray signalizuje barvou, jestli služba běží.
**DoD:**
- Po přihlášení uživatele na server je ikona agenta v systray.
- Ikona je identifikovatelná názvem agenta.
- Ikona má jednu barvu pro stav RUNNING a odlišnou barvu pro stav, kdy služba neběží.
- Tray aplikace zjišťuje stav služby s periodou 5 sekund.
- Změna stavu služby se na barvě ikony projeví nejpozději 5 sekund po té změně.

### UC1-R6
**Popis:** Z kontextového menu ikony v systray lze službu spustit, zastavit a restartovat.
**DoD:**
- Kontextové menu ikony obsahuje položky Spustit, Zastavit a Restartovat.
- Spustit převede zastavenou službu do stavu RUNNING, Zastavit běžící službu do stavu STOPPED.
- Restartovat službu zastaví a znovu spustí, výsledný stav je RUNNING.
- Stav služby po každé akci je ověřitelný příkazem `sc query ZabbixVms`.

### UC1-R7
**Popis:** Službu smí spustit, zastavit a restartovat i uživatel bez oprávnění administrátora.
**DoD:**
- Při registraci služby se jí nastaví deskriptor zabezpečení (ACL), který uživatelům bez oprávnění administrátora povoluje dotaz na stav, spuštění a zastavení služby.
- Tray aplikace běží jako neelevovaný proces a při svém startu ani při akcích z menu nevyvolá výzvu UAC.
- Akce Spustit, Zastavit a Restartovat uspějí pod účtem bez oprávnění administrátora; výsledný stav je ověřitelný přes `sc query ZabbixVms`.
- Nastavený ACL nedovoluje uživateli bez oprávnění administrátora službu odregistrovat ani změnit její konfiguraci.

### UC1-R8
**Popis:** Tray aplikace se spouští automaticky při přihlášení uživatele.
**DoD:**
- Po přihlášení uživatele na server se tray aplikace spustí bez ručního zásahu a její ikona je v systray.
- Automatické spuštění funguje i po restartu serveru.
- Automatické spuštění se nastaví při instalaci agenta, ne ručním zásahem obsluhy.

## UC2 – Nastavení agenta na konkrétní instalaci

Aktérem je obsluha serveru VMS. Cílem je nastavit agenta na danou instalaci – kam odesílat
metriky a které turbíny sledovat – bez zásahu do kódu. Spouštěčem je nasazení agenta na nový
server nebo změna instalace, například jiná turbína nebo jiný Zabbix server. Obsluha nastaví
hodnoty v konfiguraci a po restartu služby agent pracuje podle nich.

### UC2-R1
**Popis:** Konfigurace agenta je uložená v jednom souboru JSON, který vznikne serializací konfigurační třídy nástrojem jsonpickle.
**DoD:**
- Konfigurace je v kódu definovaná jako třída, jejíž členy odpovídají jednotlivým konfiguračním položkám.
- Uložený soubor je platný JSON a nese typové značky jsonpicklu, takže se načte zpět jako instance konfigurační třídy.
- Uložení a následné načtení konfigurace vrátí stejné hodnoty všech položek.

### UC2-R2
**Popis:** Konfigurace obsahuje ve společné skupině parametry odesílání do Zabbixu.
**DoD:**
- Skupina obsahuje adresu Zabbix serveru a číslo portu jeho trapperu.
- Skupina obsahuje `location` – textové označení lokality, ze kterého se skládá název hostu v Zabbixu (viz UC2-R5).
- Skupina obsahuje prodlevu mezi cykly měření v sekundách (viz UC4-R6).
- Agent odesílá metriky na adresu a port uvedené v konfiguraci.
- Změna kterékoli z těchto hodnot se projeví po restartu služby, bez úpravy kódu.

### UC2-R3
**Popis:** Konfigurace obsahuje seznam jedné až čtyř turbín, každou nastavenou samostatně.
**DoD:**
- Agent přijme konfiguraci s jednou až čtyřmi turbínami.
- Konfiguraci s prázdným seznamem turbín nebo s více než čtyřmi turbínami agent odmítne jako neplatnou a nezačne odesílat metriky.
- Hodnoty nastavené u jedné turbíny neovlivní hodnoty ostatních turbín.

### UC2-R4
**Popis:** Agent konfiguraci při svém běhu nepřepisuje.
**DoD:**
- Konfigurační soubor je po startu a zastavení služby bajtově shodný se stavem před startem.
- Hodnoty nastavené obsluhou zůstanou v souboru zachované i po restartu serveru.

### UC2-R5
**Popis:** Každá turbína je v konfiguraci popsaná názvem, identifikátorem `system_id` a seznamem bufferů.
**DoD:**
- U každé turbíny se nastaví název, `system_id` a seznam názvů bufferů.
- Seznam bufferů obsahuje žádný, jeden nebo dva buffery; konfiguraci s více než dvěma buffery agent odmítne jako neplatnou.
- Turbína bez nastaveného bufferu i turbína s jedním nastaveným bufferem je platná konfigurace.
- Metriky turbíny se odesílají do Zabbixu pod názvem hostu ve tvaru `<location>_<název turbíny>`, tedy `location` a název turbíny spojené podtržítkem.
- Název hostu je jednoznačný pro každou kombinaci lokality a turbíny, takže se metriky různých turbín ani různých lokalit nemíchají.
- `system_id` určuje, které řádky se z databáze čtou pro danou turbínu.

### UC2-R6
**Popis:** Konfigurace obsahuje ve společné skupině parametry databáze MySQL.
**DoD:**
- Skupina obsahuje adresu serveru MySQL, název databáze, uživatelské jméno a heslo.
- Skupina obsahuje název tabulky, ze které agent čte informace o turbínách (`info`).
- Agent se k databázi připojuje a čte z tabulky uvedené v konfiguraci.
- Změna kterékoli z těchto hodnot se projeví po restartu služby, bez úpravy kódu.
- Heslo je v konfiguraci uložené v otevřené podobě, bez šifrování.

### UC2-R7
**Popis:** Agent pracuje s konfigurací umístěnou v `ProgramData`; konfigurace dodaná v balíčku je jen výchozí šablona.
**DoD:**
- Agent čte konfiguraci ze souboru `C:\ProgramData\LogicElements\ZabbixVms\config.json`.
- Pokud tento soubor neexistuje, vytvoří se při prvním spuštění z výchozí konfigurace dodané v balíčku.
- Pokud soubor existuje, agent ho použije a výchozí konfiguraci z balíčku ignoruje.
- Instalace ani aktualizace balíčku obsah souboru v `ProgramData` nezmění.

### UC2-R8
**Popis:** Konfiguraci lze otevřít k editaci z kontextového menu ikony v systray.
**DoD:**
- Kontextové menu ikony obsahuje položku Otevřít konfiguraci.
- Volbou této položky se aktivní konfigurační soubor z `ProgramData` otevře v textovém editoru, který má systém přiřazený k souborům `.json`.
- Po uložení změn a restartu služby agent pracuje podle nových hodnot.
- Editace konfigurace nevyžaduje oprávnění administrátora.

## UC3 – Sada metrik odesílaných do Zabbixu

Aktérem je ten, kdo zavádí dohled v Zabbixu. Cílem je mít jednu závaznou sadu metrik, podle
které se v Zabbixu založí položky a proti které se dá ověřit, že agent odesílá právě je.
Spouštěčem je zavedení dohledu nad novou instalací nebo změna sady metrik. Sada je vedená jako
tabulka; z jejích řádků se založí položky typu Zabbix trapper a agent odesílá právě tyto
metriky. Jak agent k hodnotám metrik dochází, řeší samostatný use case.

Sada metrik odesílaných do Zabbixu:

| Klíč | Název | Typ hodnoty | Jednotka | Popis |
| --- | --- | --- | --- | --- |
| `vms.speed` | Otáčky turbíny | Numeric (float) | rpm | Aktuální otáčky turbíny |
| `vms.info_age` | Stáří info záznamu | Numeric (unsigned) | s | Doba od poslední aktualizace tabulky `info`. Hodnoty nad jeden měsíc se hlásí jako jeden měsíc. |
| `vms.timestamp_age` | Stáří timestamp dat | Numeric (unsigned) | s | Doba od posledních přijatých timestamp dat. Hodnoty nad jeden měsíc se hlásí jako jeden měsíc. |
| `vms.config_age` | Stáří konfiguračních dat | Numeric (unsigned) | s | Doba od posledních přijatých konfiguračních dat. Hodnoty nad jeden měsíc se hlásí jako jeden měsíc. |
| `vms.buf_rows_1` | Počet řádků v bufferu 1 | Numeric (unsigned) | | Počet řádků v první bufferové tabulce |
| `vms.buf_rows_2` | Počet řádků v bufferu 2 | Numeric (unsigned) | | Počet řádků v druhé bufferové tabulce |
| `vms.buf_age_1` | Stáří bufferu 1 | Numeric (unsigned) | s | Doba od posledních dat přijatých do bufferu 1. Hodnoty nad jeden měsíc se hlásí jako jeden měsíc. |
| `vms.buf_age_2` | Stáří bufferu 2 | Numeric (unsigned) | s | Doba od posledních dat přijatých do bufferu 2. Hodnoty nad jeden měsíc se hlásí jako jeden měsíc. |
| `vms.buf_bulk_1` | Doba bulk zápisu 1 | Numeric (unsigned) | ms | Doba zápisu bulk příkazu do databáze pro buffer 1 |
| `vms.buf_bulk_2` | Doba bulk zápisu 2 | Numeric (unsigned) | ms | Doba zápisu bulk příkazu do databáze pro buffer 2 |
| `vms.agent_status` | Stav agenta | Numeric (unsigned) | | 0 = agent pracuje bez chyby, 1 = varování, 2 = chyba. Popis chyby nese `vms.agent_error`. |
| `vms.agent_error` | Poslední chyba agenta | Character | | Text poslední chyby nebo varování agenta; prázdný, když je vše v pořádku. |


### UC3-R1
**Popis:** Sada metrik, které agent odesílá do Zabbixu, je vedená jako tabulka v této PRS.
**DoD:**
- Tabulka uvádí každou metriku, kterou agent odesílá.
- Agent neodesílá žádnou metriku, která v tabulce není.

### UC3-R2
**Popis:** Tabulka metrik obsahuje sloupce potřebné k založení odpovídající položky v Zabbixu.
**DoD:**
- Tabulka má sloupce Klíč, Název, Typ hodnoty, Jednotka a Popis.
- Sloupec Typ hodnoty používá názvy typů podle Zabbixu.
- Z jednoho řádku tabulky lze v Zabbixu založit položku bez doplňování dalších údajů.
- Typ položky se v tabulce neuvádí, protože všechny metriky jsou položky typu Zabbix trapper.

### UC3-R3
**Popis:** Metriky obou bufferů se odesílají vždy; u bufferu, který turbína nemá nastavený, mají hodnotu 0.
**DoD:**
- Agent odesílá metriky obou bufferů pro každou turbínu, bez ohledu na počet bufferových tabulek nastavených u turbíny.
- Metriky bufferu, který turbína nemá nastavený, mají hodnotu 0 – tedy u turbíny s jednou bufferovou tabulkou metriky druhého bufferu a u turbíny bez bufferové tabulky metriky obou.
- Klíč metriky rozlišuje, ke kterému z bufferů hodnota patří.

### UC3-R4  
**Popis:** Balíček obsahuje šablonu pro Zabbix odpovídající tabulce metrik a dokumentace obsahuje návod, podle kterého ji obsluha před nasazením do Zabbixu naimportuje.
**DoD:**
- Balíček obsahuje soubor se šablonou ve formátu YAML, který Zabbix umí naimportovat.
- Šablona obsahuje právě metriky z tabulky výše – žádnou navíc a žádnou nevynechává.
- Každá položka šablony je typu Zabbix trapper a má klíč, název, typ hodnoty a jednotku podle tabulky.
- Šablona se do Zabbixu naimportuje bez ruční úpravy souboru.
- Agent sám v Zabbixu žádnou konfiguraci nezakládá a nepotřebuje přístup k Zabbix API.
- Ve složce `doc/` je návod k nastavení Zabbixu pro tuto sadu metrik.
- Návod popisuje založení hostu `<location>_<název turbíny>`, import šablony z balíčku a přiřazení šablony tomuto hostu.
- Návod neobsahuje nic nad rámec těchto tří kroků.
- Návod je uvedený v rozcestníku v `README.md`.

## UC4 – Získávání hodnot metrik z databáze BVMS

Aktérem je agent. Cílem je naplnit sadu metrik z UC3 hodnotami z databáze `BVMS`. Spouštěčem je
každý cyklus měření. Agent pro každou turbínu z konfigurace přečte její řádek z informační
tabulky a metadata jejích bufferových tabulek, z nich spočítá hodnoty metrik a odešle je do
Zabbixu. Zdroj každé metriky určuje tabulka níže.

| Klíč metriky | Zdroj | Vstup | Pole zdroje | Výpočet |
| --- | --- | --- | --- | --- |
| `vms.speed` | řádek `info` turbíny | `info`, `system_id` | `Phase_Marker` | `1e8 / Phase_Marker * 60` |
| `vms.info_age` | řádek `info` turbíny | `info`, `system_id` | `Date` | celé sekundy mezi `Date` a časem měření |
| `vms.timestamp_age` | řádek `info` turbíny | `info`, `system_id` | `Date_Timestamp` | celé sekundy mezi `Date_Timestamp` a časem měření |
| `vms.config_age` | řádek `info` turbíny | `info`, `system_id` | `Date_Config` | celé sekundy mezi `Date_Config` a časem měření |
| `vms.buf_age_1` | řádek `info` turbíny | `info`, `system_id` | `Date_Buffer_1` | celé sekundy mezi `Date_Buffer_1` a časem měření |
| `vms.buf_age_2` | řádek `info` turbíny | `info`, `system_id` | `Date_Buffer_2` | celé sekundy mezi `Date_Buffer_2` a časem měření |
| `vms.buf_bulk_1` | řádek `info` turbíny | `info`, `system_id` | `Time_bulk_1` | přímo hodnota |
| `vms.buf_bulk_2` | řádek `info` turbíny | `info`, `system_id` | `Time_bulk_2` | přímo hodnota |
| `vms.buf_rows_1` | `information_schema.TABLES` | `database`, první bufferová tabulka turbíny | `TABLE_ROWS` | přímo hodnota |
| `vms.buf_rows_2` | `information_schema.TABLES` | `database`, druhá bufferová tabulka turbíny | `TABLE_ROWS` | přímo hodnota |
| `vms.agent_status` | vlastní stav agenta | – | – | 0, 1 nebo 2 podle průběhu cyklu |
| `vms.agent_error` | vlastní stav agenta | – | – | text poslední chyby, jinak prázdný řetězec |

### UC4-R1
**Popis:** Zdroj hodnoty každé metriky je popsaný tabulkou zdrojů v tomto use casu.
**DoD:**
- Tabulka uvádí u každé metriky ze sady v UC3 zdroj, vstup, pole zdroje a výpočet.
- Agent počítá hodnoty metrik podle této tabulky.

### UC4-R2
**Popis:** Pro každou turbínu se čte právě její řádek informační tabulky.
**DoD:**
- Agent čte řádek z tabulky, jejíž název je v konfiguraci jako `info`.
- Pro turbínu se čte řádek, jehož `SystemId` odpovídá `system_id` této turbíny.
- Hodnoty jedné turbíny se nepočítají z řádku jiné turbíny.

### UC4-R3
**Popis:** Hodnoty se z řádku informační tabulky čtou podle názvů sloupců, ne podle jejich pozice.
**DoD:**
- Agent hodnoty vybírá podle názvu sloupce uvedeného v tabulce zdrojů.
- Přidání sloupce do informační tabulky ani změna jejich pořadí nezmění hodnoty odeslaných metrik.

### UC4-R4
**Popis:** Metriky stáří jsou počtem celých sekund mezi zdrojovým datem a časem měření, saturovaným na jeden měsíc.
**DoD:**
- Hodnota metriky `*_age` je počet celých sekund mezi hodnotou zdrojového sloupce a časem měření daného cyklu.
- Přesáhne-li vypočtené stáří jeden měsíc (30 dní), odešle se hodnota jednoho měsíce; starší data už nesou tutéž informaci, že přestala chodit.
- Chybějící zdrojové datum se hlásí jako jeden měsíc, tedy stejně jako nejstarší možná hodnota; databáze pro „nikdy" zapisuje `0001-01-01`, což saturuje stejně.
- Zdrojové datum v budoucnosti se hlásí jako nula, protože metriky stáří jsou typu Numeric (unsigned) a zápornou hodnotu by Zabbix odmítl.
- Všechny metriky jedné turbíny v jednom cyklu se počítají proti témuž času měření.

### UC4-R5
**Popis:** Metriky bufferů se získávají ze dvou různých zdrojů podle toho, o kterou metriku jde.
**DoD:**
- `vms.buf_age_1` a `vms.buf_age_2` se počítají ze sloupců `Date_Buffer_1` a `Date_Buffer_2`, tedy z pevných pozic v informační tabulce.
- `vms.buf_bulk_1` a `vms.buf_bulk_2` se berou ze sloupců `Time_bulk_1` a `Time_bulk_2`, rovněž z pevných pozic.
- `vms.buf_rows_1` a `vms.buf_rows_2` se berou z `TABLE_ROWS` pro tabulku, jejíž název je první, resp. druhý v seznamu bufferů dané turbíny.
- Název bufferové tabulky z konfigurace neovlivňuje, ze kterých sloupců informační tabulky se čte stáří a bulk.
- Metriky bufferu, který turbína nemá nastavený, se odesílají s hodnotou 0; hodnoty ze sloupců informační tabulky se pro něj nepoužijí.

### UC4-R6
**Popis:** Agent opakuje cyklus měření s prodlevou, kterou lze nastavit v konfiguraci.
**DoD:**
- Prodleva se nastavuje v konfiguraci ve skupině parametrů odesílání do Zabbixu, v sekundách.
- Mezi dokončením jednoho cyklu měření a začátkem následujícího uplyne nastavená prodleva.
- Povolený rozsah je 5 až 120 sekund; konfiguraci s hodnotou mimo tento rozsah agent odmítne jako neplatnou.
- Není-li prodleva v konfiguraci uvedená, použije se 5 sekund, takže konfigurace zapsaná starší verzí agenta zůstává platná.
- Jeden cyklus zahrnuje odeslání metrik všech turbín z konfigurace.

## UC5 – Hlášení chyb a provozních událostí

Aktérem je obsluha serveru VMS. Cílem je poznat, že agent sám nefunguje nebo že jeho hodnoty
nedoputují do Zabbixu, a mít podklad pro nápravu. Spouštěčem je chyba za běhu: neplatná
konfigurace, nedostupná databáze nebo hodnoty odmítnuté Zabbixem. Agent události zapisuje do
logovacího souboru a ty zásadní i do Windows Event Logu.

### UC5-R1
**Popis:** Agent zapisuje provozní události a chyby do logovacího souboru.
**DoD:**
- Logovací soubor je ve stejné složce jako konfigurace, tedy `C:\ProgramData\LogicElements\ZabbixVms\`.
- Každý záznam obsahuje časovou značku, úroveň a text události.
- Zaznamenává se start a zastavení služby, neplatná konfigurace, nedostupnost MySQL i Zabbixu a hodnoty odmítnuté Zabbixem.
- Logovací soubor se rotuje po dosažení 1 MB a uchovává se posledních 5 souborů, takže objem logů neroste bez omezení.
- Do logu smí zapisovat služba i tray aplikace, aniž by si navzájem poškodily záznamy.

### UC5-R2
**Popis:** Agent zapisuje start, zastavení a chyby bránící běhu do Windows Event Logu.
**DoD:**
- Start a zastavení služby se objeví v Event Vieweru pod zdrojem `ZabbixVms`.
- Chyba, která agentovi brání odesílat metriky, se zapíše jako událost typu Error.
- Běžné provozní záznamy se do Event Logu nezapisují; ty zůstávají jen v logovacím souboru.

### UC5-R3
**Popis:** Agent odesílá svůj vlastní stav do Zabbixu jako dvojici metrik.
**DoD:**
- V každém cyklu odešle agent `vms.agent_status` a `vms.agent_error` na každý host turbíny, kterou má v konfiguraci.
- `vms.agent_status` má hodnotu 0, proběhl-li celý cyklus bez chyby, 1 při varování, po kterém agent pokračuje, a 2 při chybě, která mu brání získat nebo odeslat hodnoty metrik.
- `vms.agent_error` nese text poslední chyby nebo varování; při stavu 0 je prázdný.
- Text chyby odpovídá záznamu v logovacím souboru a zkracuje se na 255 znaků, aby se vešel do položky typu Character.

Sada triggerů, které šablona obsahuje:

| Název triggeru | Klíč metriky | Podmínka | Priorita |
| --- | --- | --- | --- |
| Agent hlásí chybu nebo varování | `vms.agent_status` | `last({METRIC})>0` | AVERAGE |
| Z hostu nepřišla žádná hodnota 5m | `vms.agent_status` | `nodata({METRIC},5m)=1` | HIGH |
| Chyba agenta: {ITEM.VALUE} | `vms.agent_error` | `length(last({METRIC}))>0` | AVERAGE |

`{METRIC}` v podmínce zastupuje odkaz na metriku ve tvaru `/<název šablony>/<klíč metriky>`.
Klíč metriky určuje i to, pod kterou položkou šablony trigger v exportu leží.

### UC5-R4
**Popis:** Šablona pro Zabbix obsahuje mapování stavů a triggery vedené jako tabulka v této PRS.
**DoD:**
- Šablona obsahuje value map, která u `vms.agent_status` překládá hodnoty 0, 1 a 2 na text.
- Šablona obsahuje právě triggery z tabulky výše – žádný navíc a žádný nevynechává.
- Každý trigger má název, podmínku a prioritu podle svého řádku tabulky.
- Každý trigger se odkazuje na klíč metriky, který je v tabulce metrik v UC3.
- Tabulka obsahuje trigger na stav agenta, trigger na neprázdný `vms.agent_error` s textem chyby ve jméně a trigger na to, že na host nedorazila žádná hodnota po dobu 5 minut; ten pokrývá i případ, kdy agent neběží nebo je Zabbix nedostupný a žádnou metriku odeslat nelze.
