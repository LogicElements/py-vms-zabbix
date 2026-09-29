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
| UC1-R8 | Automatické spuštění tray aplikace při přihlášení uživatele | Hotovo | N/A |
| UC2-R1 | Konfigurace jako JSON dump konfigurační třídy přes jsonpickle | Hotovo | tests/test_config.py |
| UC2-R2 | Skupina parametrů odesílání do Zabbixu: spojení, `location` a prodleva | Hotovo | tests/test_sender.py |
| UC2-R3 | Seznam 1 až 4 turbín, každá nastavená samostatně | Hotovo | tests/test_config.py |
| UC2-R4 | Agent konfiguraci při svém běhu nepřepisuje | Hotovo | tests/test_config.py |
| UC2-R5 | Turbína popsaná názvem, system_id a nejvýše dvěma buffery | Hotovo | tests/test_sender.py |
| UC2-R6 | Skupina parametrů databáze MySQL: spojení a tabulka `info` | Hotovo | tests/test_collector.py |
| UC2-R7 | Aktivní konfigurace v ProgramData, v balíčku jen výchozí šablona | Hotovo | tests/test_config.py |
| UC2-R8 | Otevření datové složky z kontextového menu ikony | Hotovo | tests/test_tray.py |
| UC2-R9 | Chybějící položku doplní výchozí hodnota jen u položek z novějších verzí | Hotovo | tests/test_config.py |
| UC2-R10 | Zápis nových položek do konfigurace při aktualizaci instalačním skriptem | Hotovo | tests/test_config.py, tests/test_service.py |
| UC3-R1 | Sada odesílaných metrik vedená jako tabulka v PRS | Hotovo | tests/test_metrics.py, tests/test_agent.py |
| UC3-R2 | Sloupce tabulky dostačují k založení položky v Zabbixu | Hotovo | tests/test_metrics.py |
| UC3-R3 | Metriky bufferů jako souhrn přes nastavené buffery turbíny | Hotovo | tests/test_collector.py |
| UC3-R4 | Šablona pro Zabbix v balíčku a stručný návod k jejímu nasazení v `doc/` | Hotovo | tests/test_template.py |
| UC4-R1 | Zdroje hodnot metrik popsané tabulkou | Hotovo | tests/test_collector.py |
| UC4-R2 | Řádek `info` čtený pro každou turbínu podle jejího `system_id` | Hotovo | tests/test_collector_db.py |
| UC4-R3 | Čtení sloupců `info` podle názvu, ne podle pozice | Hotovo | tests/test_collector_db.py |
| UC4-R4 | Stáří v celých sekundách proti času měření, saturované na jeden měsíc | Hotovo | tests/test_collector.py |
| UC4-R5 | Buffery: stáří jako maximum, bulk a řádky jako součet přes nastavené buffery | Hotovo | tests/test_collector.py |
| UC4-R6 | Prodleva mezi cykly měření nastavitelná v rozsahu 5 až 120 sekund | Hotovo | tests/test_agent.py |
| UC4-R7 | Hodnoty z `information_schema` aktuální, ne z mezipaměti statistik MySQL 8 | Hotovo | tests/test_collector.py |
| UC4-R8 | Každý dotaz agenta vidí databázi v aktuálním stavu, ne snímek otevřené transakce | Hotovo | tests/test_collector.py, tests/test_collector_db.py |
| UC5-R1 | Logovací soubor s provozními událostmi a chybami | Hotovo | tests/test_log.py |
| UC5-R2 | Start, zastavení a zásadní chyby ve Windows Event Logu | Hotovo | N/A |
| UC5-R3 | Vlastní stav agenta odesílaný na host serveru jako dvojice metrik | Hotovo | tests/test_agent.py |
| UC5-R4 | Triggery turbín a value map stavu agenta v šablonách | Hotovo | tests/test_template.py, tests/test_triggers.py |
| UC6-R1 | Seznam prefixů tabulek surových dat v konfiguraci turbíny | Hotovo | tests/test_config.py |
| UC6-R2 | Tabulka patří k prefixu podle celého názvu `<prefix>_<datum>` | Hotovo | tests/test_collector.py, tests/test_collector_db.py |
| UC6-R3 | Počet tabulek jako největší počet přes prefixy, chyba exportu od 3 tabulek | Hotovo | tests/test_collector.py, tests/test_triggers.py |
| UC6-R4 | Stáří zápisu do nejnovější tabulky, chyba po 5 minutách mimo klid turbíny | Hotovo | tests/test_collector.py, tests/test_triggers.py |
| UC6-R5 | Nová tabulka bez zápisu se první minutu nehlásí jako zastavený zápis | Hotovo | tests/test_collector.py |
| UC7-R1 | Skupina `server` v konfiguraci: povinný host serveru a čtení z IPP | Hotovo | tests/test_config.py, tests/test_agent.py |
| UC7-R2 | Nabití baterie UPS z IPP odesílané jako `ups.charge` na host serveru | Hotovo | tests/test_ups.py, tests/test_agent.py |
| UC7-R3 | Nezjištěné nabití jako chyba na hostu serveru, bez `ups.charge` | Hotovo | tests/test_ups.py, tests/test_agent.py |
| UC7-R4 | Stav agenta na hostu serveru shrnuje čtení z databáze i z IPP | Hotovo | tests/test_agent.py |
| UC7-R5 | Samostatná šablona pro host serveru | Hotovo | tests/test_template.py |
| UC7-R6 | Chyba napájení při nabití pod mezí `{$VMS.UPS.CHARGE.MIN}` | Hotovo | tests/test_triggers.py, tests/test_template.py |
| UC7-R7 | Dokumentace nasazení hostu serveru, sledování UPS a jeho chyb | Hotovo | N/A |

## Účel projektu

Na turbíně běží sada na sebe navazujících aplikací VMS: sběr dat z VMS elektroniky, výpočet
vibrací z nasbíraných dat a přenos vypočítaných hodnot na server TLCS. Když kterákoli z nich
přestane běžet nebo se dostane do nestandardního stavu, přenos dat se zastaví nebo začnou
chybět hodnoty.

Agent proto vystavuje stav těchto aplikací, stav turbíny a napájení serveru v Zabbixu, kde už
je zavedený dohled a alerting. Přínosem je včasný report o výpadku běhu softwaru nebo
o nestandardním stavu, aby se dal řešit hned.

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
hodnoty v konfiguraci a po restartu služby agent pracuje podle nich. Při aktualizaci agenta
se do konfigurace doplní položky, které přinesla nová verze, takže je obsluha vidí a může je
nastavit.

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
- Instalace ani aktualizace balíčku přes `pip` obsah souboru v `ProgramData` nezmění; jedinou výjimkou je doplnění nových položek instalačním skriptem podle UC2-R10.

### UC2-R8
**Popis:** Z kontextového menu ikony v systray lze otevřít datovou složku agenta, ve které leží konfigurace i log.
**DoD:**
- Kontextové menu ikony obsahuje položku Otevřít datovou složku.
- Volbou této položky se otevře složka `C:\ProgramData\LogicElements\ZabbixVms` a jsou v ní vidět konfigurační soubor i logovací soubor.
- Konfiguraci lze z otevřené složky otevřít k editaci; po uložení změn a restartu služby agent pracuje podle nových hodnot.
- Otevření složky ani editace konfigurace nevyžadují oprávnění administrátora.

### UC2-R9
**Popis:** Položka, která v konfiguraci chybí, se doplní výchozí hodnotou jen tehdy, když přibyla v novější verzi agenta.
**DoD:**
- Položky přidané po první verzi agenta, tedy `period` ve skupině odesílání do Zabbixu, `raw_prefixes` u turbíny a skupina `server` (UC7-R1), se při načtení konfigurace, která je nemá, doplní hodnotou, se kterou agent pracuje stejně jako verze, která je neznala: 5 sekund, prázdný seznam a skupina `server` s vypnutým sledováním UPS.
- Konfiguraci, ve které chybí jiná položka, například `system_id` turbíny nebo `location`, agent odmítne jako neplatnou a v chybě uvede, která položka chybí.
- Chybějící skupina `server` a skupina s prázdným `host` dostanou `host` složený z `location` a `_server`, například `Praha_server`; `host` s vyplněným jménem se nemění.
- Doplnění probíhá jen v paměti, soubor konfigurace se jím nezmění (UC2-R4).

### UC2-R10
**Popis:** Při aktualizaci agenta instalačním skriptem se do souboru konfigurace zapíšou položky, které přinesla nová verze.
**DoD:**
- Instalační skript `install.ps1` po výměně balíčku a před spuštěním služby zapíše do konfigurace v `ProgramData` položky podle UC2-R9, které v ní chybí, s jejich výchozí hodnotou.
- Hodnoty, které už v konfiguraci jsou, zůstanou beze změny.
- Původní soubor zůstane vedle nového jako `config.json.bak`.
- Když v konfiguraci nic nechybí nebo když konfigurace ještě neexistuje, soubor zůstane beze změny a záloha nevznikne.
- Konfiguraci, kterou agent odmítá jako neplatnou, skript nemění; ohlásí to a pokračuje.
- Totéž jde spustit ručně příkazem `zabbixvms-service complete-config`.

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
| `vms.buf_rows` | Počet řádků v bufferech | Numeric (unsigned) | | Součet počtu řádků přes bufferové tabulky turbíny |
| `vms.buf_age` | Stáří bufferů | Numeric (unsigned) | s | Doba od posledních dat přijatých do toho bufferu turbíny, který je na tom nejhůř. Hodnoty nad jeden měsíc se hlásí jako jeden měsíc. |
| `vms.buf_bulk` | Doba bulk zápisu | Numeric (unsigned) | ms | Součet doby zápisu bulk příkazů do databáze přes buffery turbíny |
| `vms.raw_tables` | Počet tabulek surových dat | Numeric (unsigned) | | Největší počet tabulek surových dat se stejným prefixem přes prefixy turbíny |
| `vms.raw_write_age` | Stáří zápisu surových dat | Numeric (unsigned) | s | Doba od posledního zápisu do nejnovější tabulky surových dat u toho prefixu turbíny, který je na tom nejhůř. Hodnoty nad jeden měsíc se hlásí jako jeden měsíc. |

Stav agenta se na hosty turbín neodesílá; nese ho host serveru (UC7).

### UC3-R1
**Popis:** Sada metrik, které agent odesílá do Zabbixu, je vedená jako tabulka v této PRS.
**DoD:**
- Tabulka výše uvádí každou metriku, kterou agent odesílá na hosty turbín; metriky hostu serveru uvádí tabulka v UC7.
- Agent neodesílá žádnou metriku, která v příslušné tabulce není.

### UC3-R2
**Popis:** Tabulka metrik obsahuje sloupce potřebné k založení odpovídající položky v Zabbixu.
**DoD:**
- Tabulka má sloupce Klíč, Název, Typ hodnoty, Jednotka a Popis.
- Sloupec Typ hodnoty používá názvy typů podle Zabbixu.
- Z jednoho řádku tabulky lze v Zabbixu založit položku bez doplňování dalších údajů.
- Typ položky se v tabulce neuvádí, protože všechny metriky jsou položky typu Zabbix trapper.

### UC3-R3
**Popis:** Metriky bufferů jsou souhrnem přes bufferové tabulky turbíny, ne metrikou každé z nich.
**DoD:**
- Agent odesílá tři metriky bufferů – počet řádků, stáří a dobu bulk zápisu – bez ohledu na to, kolik bufferových tabulek má turbína nastavených.
- Počet řádků a doba bulk zápisu jsou součtem přes nastavené buffery, stáří je největší ze stáří nastavených bufferů.
- Buffer, který turbína nemá nastavený, do souhrnu nevstupuje; turbína s jednou bufferovou tabulkou proto hlásí hodnoty právě té jedné a turbína bez bufferu hlásí u všech tří metrik 0.

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
- Kromě těchto tří kroků návod popisuje nastavení, která se dělají na straně Zabbix serveru a týkají se téhle sady metrik: mez otáček a odesílání e-mailů při problému.
- Návod je uvedený v rozcestníku v `README.md`.

## UC4 – Získávání hodnot metrik z databáze BVMS

Aktérem je agent. Cílem je naplnit sadu metrik z UC3 hodnotami z databáze `BVMS`. Spouštěčem je
každý cyklus měření. Agent pro každou turbínu z konfigurace přečte její řádek z informační
tabulky a metadata jejích bufferových tabulek a tabulek surových dat (UC6), z nich spočítá
hodnoty metrik a odešle je do Zabbixu. Zdroj každé metriky určuje tabulka níže.

| Klíč metriky | Zdroj | Vstup | Pole zdroje | Výpočet |
| --- | --- | --- | --- | --- |
| `vms.speed` | řádek `info` turbíny | `info`, `system_id` | `Phase_Marker` | `1e8 / Phase_Marker * 60`; výsledek menší než 3 rpm se hlásí jako 0 |
| `vms.info_age` | řádek `info` turbíny | `info`, `system_id` | `Date` | celé sekundy mezi `Date` a časem měření |
| `vms.timestamp_age` | řádek `info` turbíny | `info`, `system_id` | `Date_Timestamp` | celé sekundy mezi `Date_Timestamp` a časem měření |
| `vms.config_age` | řádek `info` turbíny | `info`, `system_id` | `Date_Config` | celé sekundy mezi `Date_Config` a časem měření |
| `vms.buf_age` | řádek `info` turbíny | `info`, `system_id` | `Date_Buffer_1`, `Date_Buffer_2` | větší ze stáří obou sloupců, přes nastavené buffery |
| `vms.buf_bulk` | řádek `info` turbíny | `info`, `system_id` | `Time_bulk_1`, `Time_bulk_2` | součet hodnot přes nastavené buffery |
| `vms.buf_rows` | `information_schema.TABLES` | `database`, bufferové tabulky turbíny | `TABLE_ROWS` | součet hodnot přes nastavené buffery |
| `vms.raw_tables` | `information_schema.TABLES` | `database`, prefixy surových dat turbíny | `TABLE_NAME` | počet tabulek každého prefixu (UC6-R2), největší z nich |
| `vms.raw_write_age` | `information_schema.TABLES` | `database`, prefixy surových dat turbíny | `TABLE_NAME`, `UPDATE_TIME`, `CREATE_TIME` | stáří `UPDATE_TIME` nejnovější tabulky každého prefixu, u nové tabulky bez zápisu první minutu stáří `CREATE_TIME` (UC6-R5), největší z nich |

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
- `vms.buf_age` je největší ze stáří spočítaných ze sloupců `Date_Buffer_1` a `Date_Buffer_2`, tedy z pevných pozic v informační tabulce.
- `vms.buf_bulk` je součtem sloupců `Time_bulk_1` a `Time_bulk_2`, rovněž z pevných pozic.
- `vms.buf_rows` je součtem `TABLE_ROWS` pro tabulky, jejichž názvy jsou v seznamu bufferů dané turbíny.
- Sloupec informační tabulky patří k bufferu podle jeho pořadí v seznamu; název bufferové tabulky z konfigurace neurčuje, ze kterého sloupce se stáří a bulk čtou.
- Buffer, který turbína nemá nastavený, do souhrnu nevstupuje; jemu odpovídající sloupce informační tabulky se nepoužijí.

### UC4-R6
**Popis:** Agent opakuje cyklus měření s prodlevou, kterou lze nastavit v konfiguraci.
**DoD:**
- Prodleva se nastavuje v konfiguraci ve skupině parametrů odesílání do Zabbixu, v sekundách.
- Mezi dokončením jednoho cyklu měření a začátkem následujícího uplyne nastavená prodleva.
- Povolený rozsah je 5 až 120 sekund; konfiguraci s hodnotou mimo tento rozsah agent odmítne jako neplatnou.
- Není-li prodleva v konfiguraci uvedená, použije se 5 sekund, takže konfigurace zapsaná starší verzí agenta zůstává platná.
- Jeden cyklus zahrnuje odeslání metrik všech turbín z konfigurace.

### UC4-R7
**Popis:** Hodnoty z `information_schema.TABLES` agent čte aktuální, ne z mezipaměti statistik MySQL.
**DoD:**
- Agent si pro své připojení k MySQL nastaví `information_schema_stats_expiry` na 0, takže MySQL 8 čte `TABLE_ROWS` a `UPDATE_TIME` při každém dotazu přímo z úložiště, ne z mezipaměti obnovované ve výchozím stavu jednou denně.
- Nastavení platí jen pro připojení agenta, globální nastavení serveru se nemění.
- Nastavení se obnoví při každém novém připojení agenta k databázi.
- Na serveru, který tuto proměnnou nezná (MySQL 5.7), se agent připojí a pracuje beze změny.

### UC4-R8
**Popis:** Každý dotaz agenta vidí databázi v aktuálním stavu, ne snímek z počátku otevřené transakce.
**DoD:**
- Připojení agenta k MySQL pracuje v režimu autocommit, takže agent nedrží otevřenou transakci a každý dotaz vidí data potvrzená do chvíle svého spuštění.
- Tabulka surových dat založená nebo smazaná za běhu agenta se v hodnotách projeví v nejbližším cyklu, bez restartu služby a bez nového připojení.
- Totéž platí pro řádek informační tabulky a pro buffery uložené v InnoDB.

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
**Popis:** Agent odesílá svůj vlastní stav do Zabbixu jako dvojici metrik na host serveru.
**DoD:**
- V každém cyklu odešle agent `vms.agent_status` a `vms.agent_error` na host serveru z konfigurace (`server.host`), i když je sledování UPS vypnuté; na hosty turbín je neodesílá.
- Stav shrnuje celý cyklus, tedy čtení z databáze i z IPP (UC7): `vms.agent_status` má hodnotu 0, proběhl-li celý cyklus bez chyby, 1 při varování, po kterém agent pokračuje, a 2 při chybě, která mu brání získat hodnoty metrik nebo kvůli které je Zabbix odmítne. Při více problémech v jednom cyklu je stav nejhorší z nich.
- Nedostupnost Zabbix serveru se do metrik nehlásí vůbec: hlášení by k němu dorazilo až po obnovení spojení, kdy už popisuje něco, co skončilo. Agent takový cyklus přejde a po pěti neúspěšných cyklech za sebou o tom napíše do logu; v Zabbixu se výpadek pozná chybějícími daty.
- `vms.agent_error` nese text poslední chyby nebo varování, při více problémech jsou texty spojené středníkem; při stavu 0 je prázdný.
- Text chyby nebo varování, který se týká konkrétní turbíny, začíná jejím názvem (`<název turbíny>: <text>`); text chyby, která se žádné turbíny netýká (spojení s databází, IPP), název turbíny neobsahuje.
- Text odpovídá záznamu v logovacím souboru a zkracuje se na 255 znaků, aby se vešel do položky typu Character.

Sada triggerů, které šablona turbín obsahuje:

| Název triggeru | Klíč metriky | Podmínka | Priorita | Závisí na |
| --- | --- | --- | --- | --- |
| Turbína pod nominálními otáčkami: {ITEM.VALUE} | `vms.speed` | `last({METRIC})<{$VMS.SPEED.NOMINAL}` | AVERAGE | – |
| Chyba databáze VMS setupu: {ITEM.VALUE} | `vms.info_age` | `last({METRIC})>5m` | HIGH | – |
| Chyba timestamp socketu: {ITEM.VALUE} | `vms.timestamp_age` | `last({METRIC})>5m` | HIGH | – |
| Chyba konfiguračního socketu: {ITEM.VALUE} | `vms.config_age` | `last({METRIC})>5m` | HIGH | – |
| Chyba SW analýzy čtení bufferu: {ITEM.VALUE} | `vms.buf_rows` | `last({METRIC})>100000` | HIGH | – |
| Chyba ukládání do bufferu: {ITEM.VALUE} | `vms.buf_age` | `last({METRIC})>5m` | HIGH | Turbína pod nominálními otáčkami: {ITEM.VALUE} |
| Chyba exportu surových dat: {ITEM.VALUE} | `vms.raw_tables` | `last({METRIC})>2` | HIGH | – |
| Chyba zápisu surových dat: {ITEM.VALUE} | `vms.raw_write_age` | `last({METRIC})>5m` | HIGH | Turbína pod nominálními otáčkami: {ITEM.VALUE} |
| Z hostu nepřišla žádná hodnota 5m | `vms.speed` | `nodata({METRIC},5m)=1` | HIGH | – |

`{METRIC}` v podmínce zastupuje odkaz na metriku ve tvaru `/<název šablony>/<klíč metriky>`.
Klíč metriky určuje i to, pod kterou položkou šablony trigger v exportu leží.

Sloupec **Závisí na** znamená závislost triggerů v Zabbixu: dokud je uvedený trigger
v problémovém stavu, závislý trigger se neuplatní. Zatím ho mají vyplněný dva triggery,
nad `vms.buf_age` a nad `vms.raw_write_age`: stojící turbína do bufferu nic neukládá a
nezapisuje ani surová data, takže rostoucí stáří zápisu je v takové chvíli očekávané, ne
chyba. Ostatní zdroje běží bez ohledu na otáčky a jejich triggery hlásí pořád; počet tabulek
surových dat při klidu neroste, protože nové tabulky nevznikají. Přibýt může kterýkoli další
– stačí do sloupce doplnit jméno blokujícího triggeru.

Mez otáček nese makro šablony:

| Makro | Výchozí hodnota | Význam |
| --- | --- | --- |
| `{$VMS.SPEED.NOMINAL}` | 2500 | Otáčky, pod kterými se turbína nepovažuje za běžící |

Makro jde přepsat na hostu, takže turbína s jinými nominálními otáčkami nepotřebuje vlastní
šablonu.

### UC5-R4
**Popis:** Šablona turbín obsahuje triggery vedené jako tabulka v této PRS a šablona serveru value map stavu agenta.
**DoD:**
- Šablona serveru obsahuje value map, která u `vms.agent_status` překládá hodnoty 0, 1 a 2 na text; šablona turbín value map neobsahuje.
- Šablona turbín obsahuje právě triggery z tabulky výše – žádný navíc a žádný nevynechává.
- Každý trigger má název, podmínku a prioritu podle svého řádku tabulky.
- Trigger, který má v tabulce vyplněný sloupec Závisí na, je v exportu závislý na triggeru toho jména, takže se neuplatní, dokud je blokující trigger v problémovém stavu.
- Šablona obsahuje makra z tabulky maker i s výchozími hodnotami a každé makro použité v podmínce triggeru je v ní deklarované.
- Každý trigger se odkazuje na klíč metriky, který je v tabulce metrik v UC3.
- Tabulka obsahuje trigger na to, že na host turbíny nedorazila hodnota `vms.speed` po dobu 5 minut; ten pokrývá i případ, kdy agent neběží, databáze je nedostupná nebo je Zabbix nedostupný a žádnou metriku odeslat nelze.

## UC6 – Sledování ukládání surových dat VMS a TVMS

Aktérem je ten, kdo dohlíží na přenos surových dat. Cílem je poznat, že se surová data
přestala ukládat nebo předávat k nám. Spouštěčem je každý cyklus měření.

Surová data ukládají do databáze `BVMS` dva systémy, VMS a TVMS, a oba stejně: založí tabulku
`<prefix>_<datum>` a zapisují do ní. Po uplynutí periody založí novou, tu předchozí vyexportují
do textového souboru, smažou ji z databáze, export zabalí do zipu a přenesou k nám. Oba se
liší jen periodou a tvarem data v názvu:

| Systém | Perioda | Datum v názvu | Prefixy |
| --- | --- | --- | --- |
| VMS | nastavitelná, teď 4 h | `yyyymmddHHMMSS` | `btt_tg11` (EDU TG11), `btt_tg1` (ETE TG1), `btt_tg2a`, `btt_tg2b`, `btt_tg2c` (ETE TG2) |
| TVMS | 24 h | `yyyymmdd` | `tg11_out`, `tg12_out` (RB1), `tvms_tgXY` (RB2 až RB4) |

Jedna turbína může mít prefixy obou systémů a hlásí se pod svým hostem. Agent sleduje dvě
věci: kolik tabulek jednoho prefixu v databázi je, protože hromadící se tabulky znamenají,
že neběží export, a jak dlouho se do nejnovější tabulky nezapsalo. Za klidu turbíny se surová
data nezapisují a u VMS nevznikají ani nové tabulky. Nová tabulka je po založení chvíli
prázdná, než do ní systém zapíše první data, a cyklus agenta může padnout právě do té chvíle.

Stáří nejnovější tabulky ani existence tabulky pro dnešní den se nesledují. Agent proto
nepozná, že přestaly vznikat nové tabulky, když se do poslední dál zapisuje, a za klidu
turbíny nepozná výpadek TVMS.

### UC6-R1
**Popis:** Každá turbína má v konfiguraci seznam prefixů tabulek surových dat.
**DoD:**
- U každé turbíny se nastaví seznam prefixů, ve kterém mohou být prefixy VMS i TVMS zároveň.
- Prázdný seznam je platná konfigurace; turbína bez prefixu hlásí u obou metrik surových dat 0.
- Prefix obsahuje jen písmena bez diakritiky, číslice a podtržítko; konfiguraci s jiným prefixem agent odmítne jako neplatnou.
- Konfigurace zapsaná starší verzí agenta, která seznam prefixů nemá, zůstává platná a její turbíny mají seznam prázdný.

### UC6-R2
**Popis:** Tabulka surových dat patří k prefixu podle celého svého názvu.
**DoD:**
- K prefixu patří tabulka, jejíž název je prefix, podtržítko a datum ve tvaru `yyyymmdd` nebo `yyyymmddHHMMSS`, a nic víc.
- Tabulka, jejíž datum není platné datum nebo čas, k prefixu nepatří.
- Tabulka jiného prefixu, který daným prefixem jen začíná, k němu nepatří: `btt_tg11_20260925120000` nepatří k `btt_tg1` a `btt_tg2a_20260925120000` nepatří k `btt_tg2`.
- Tabulky se hledají v databázi z konfigurace.
- Nejnovější tabulkou prefixu je ta s nejnovějším datem v názvu; datum se čte v místním čase serveru.

### UC6-R3
**Popis:** Počet tabulek surových dat je největší počet tabulek jednoho prefixu přes prefixy turbíny.
**DoD:**
- Pro každý prefix turbíny se spočítají tabulky, které k němu patří; `vms.raw_tables` je největší z těchto počtů.
- Prefix bez tabulek do počtu přispívá nulou.
- Šablona obsahuje trigger, který hlásí chybu exportu, když má jeden prefix 3 a více tabulek.

### UC6-R4
**Popis:** Stáří zápisu surových dat je stáří posledního zápisu do nejnovější tabulky u toho prefixu turbíny, který je na tom nejhůř.
**DoD:**
- Pro každý prefix se stáří zápisu počítá z `UPDATE_TIME` jeho nejnovější tabulky podle UC4-R4; `vms.raw_write_age` je největší z nich.
- Zápis do starší tabulky prefixu stáří zápisu nesnižuje.
- Prefix bez tabulky i tabulka bez `UPDATE_TIME` se hlásí jako jeden měsíc; výjimkou je nově založená tabulka podle UC6-R5.
- Šablona obsahuje trigger, který hlásí chybu zápisu, když stáří zápisu přesáhne 5 minut, a je závislý na triggeru Turbína pod nominálními otáčkami.

### UC6-R5
**Popis:** Nová tabulka surových dat, do které se ještě nezapsalo, se první minutu po svém založení nehlásí jako zastavený zápis.
**DoD:**
- U nejnovější tabulky prefixu bez `UPDATE_TIME`, od jejíhož založení podle `CREATE_TIME` neuplynula 1 minuta, se stáří zápisu počítá od `CREATE_TIME`.
- Od uplynutí 1 minuty od založení se tabulka bez `UPDATE_TIME` hlásí podle UC6-R4 jako jeden měsíc.
- Tabulka, do které se už zapsalo, má stáří zápisu podle `UPDATE_TIME` bez ohledu na to, kdy vznikla.
- Minuta se počítá od `CREATE_TIME`, ne od data v názvu tabulky.

## UC7 – Sledování napájení serveru z UPS

Aktérem je ten, kdo dohlíží na provoz serveru VMS. Cílem je poznat včas, že server běží
z baterie UPS a hrozí jeho vypnutí. Spouštěčem je každý cyklus měření.

Servery napájí UPS Eaton, kterou spravuje Eaton Intelligent Power Protector (IPP). UPS je
k IPP připojená přes USB nebo po síti; IPP obě připojení vystavuje stejně ve svém webovém
rozhraní na serveru. Agent se k tomuto rozhraní přihlásí stejně jako prohlížeč, přečte
nabití baterie a odešle ho na host serveru. Host serveru nese metriky společné celému
serveru, ne jedné turbíně; UPS je první z nich a další mohou přibýt vedle ní. Nese také stav
agenta (UC5-R3), a proto existuje na každé instalaci, i když se UPS nesleduje.

Sada metrik odesílaných na host serveru:

| Klíč | Název | Typ hodnoty | Jednotka | Popis |
| --- | --- | --- | --- | --- |
| `ups.charge` | Nabití baterie UPS | Numeric (unsigned) | % | Nabití baterie UPS podle IPP; při více UPS nejnižší z nich |
| `vms.agent_status` | Stav agenta | Numeric (unsigned) | | 0 = cyklus proběhl bez chyby, 1 = varování, 2 = chyba při čtení z databáze nebo z IPP. Popis chyby nese `vms.agent_error`. |
| `vms.agent_error` | Poslední chyba agenta | Character | | Text poslední chyby nebo varování agenta, u turbíny s jejím názvem na začátku; prázdný, když je vše v pořádku. |

| Klíč metriky | Zdroj | Pole zdroje | Výpočet |
| --- | --- | --- | --- |
| `ups.charge` | IPP, `data_srv.js?action=loadNodeData` | `UPS.PowerSummary.RemainingCapacity` | nejnižší hodnota přes uzly UPS v IPP |

Sada triggerů šablony serveru:

| Název triggeru | Klíč metriky | Podmínka | Priorita |
| --- | --- | --- | --- |
| Chyba napájení: {ITEM.VALUE} | `ups.charge` | `last({METRIC})<{$VMS.UPS.CHARGE.MIN}` | HIGH |
| Agent hlásí chybu nebo varování | `vms.agent_status` | `last({METRIC})>0` | WARNING |
| Z hostu nepřišla žádná hodnota 5m | `vms.agent_status` | `nodata({METRIC},5m)=1` | HIGH |
| Chyba agenta: {ITEM.VALUE} | `vms.agent_error` | `length(last({METRIC}))>0` | AVERAGE |

Makra šablony serveru:

| Makro | Výchozí hodnota | Význam |
| --- | --- | --- |
| `{$VMS.UPS.CHARGE.MIN}` | 50 | Nabití baterie v %, pod kterým se hlásí chyba napájení |

### UC7-R1
**Popis:** Konfigurace obsahuje skupinu `server` s názvem hostu serveru a s podskupinou `ups` pro čtení z IPP.
**DoD:**
- Skupina `server` obsahuje `host` – celý název hostu serveru v Zabbixu; neskládá se z `location` a nastavuje se nezávisle na něm.
- Podskupina `ups` obsahuje `enabled`, adresu webového rozhraní IPP `url` s výchozí hodnotou `https://localhost:4680`, uživatelské jméno `login` a heslo `password` v otevřené podobě.
- Při `enabled: false` agent IPP nečte a `ups.charge` neodesílá; stav agenta (UC5-R3) na host serveru odesílá dál.
- Konfiguraci, jejíž `host` zůstal i po doplnění podle UC2-R9 prázdný, agent odmítne jako neplatnou bez ohledu na to, je-li sledování UPS zapnuté, protože host serveru nese stav agenta.
- Chybějící skupina `server` se doplní podle UC2-R9 s vypnutým sledováním UPS a s `host` složeným z `location` a `_server`; totéž dostane skupina z verze 0.3.x s prázdným `host`.

### UC7-R2
**Popis:** Agent v každém cyklu přečte z IPP nabití baterie UPS a odešle ho jako `ups.charge` na host serveru.
**DoD:**
- Agent se k IPP na adrese z konfigurace přihlásí stejně jako jeho webové rozhraní: vyžádá si výzvu `user_srv.js?action=queryLoginChallenge` a odešle `loginUser` s heslem ve tvaru HMAC-SHA1, jehož klíčem je SHA1 hesla v šestnáctkovém zápisu a zprávou výzva.
- Certifikát IPP agent neověřuje, protože IPP používá vlastní self-signed certifikát.
- Získané `sessionID` agent používá i v dalších cyklech; přihlásí se znovu, až když ho IPP odmítne, a to ještě v tomtéž cyklu.
- Uzly UPS jsou uzly IPP, jejichž `System.Tag` obsahuje `UPS`; `ups.charge` je nejnižší `UPS.PowerSummary.RemainingCapacity` z nich.
- Čtení UPS probíhá v každém cyklu měření, tedy se stejnou prodlevou jako čtení turbín (UC4-R6).
- Na serveru s IPP 1.73 a UPS připojenou přes USB se hodnota `ups.charge` v Zabbixu shoduje s nabitím, které ukazuje webové rozhraní IPP.

### UC7-R3
**Popis:** Když agent nabití z IPP nezjistí, ohlásí na hostu serveru chybu a `ups.charge` neodešle.
**DoD:**
- Chybou je nedostupné rozhraní IPP, odmítnuté přihlášení, odpověď v neočekávaném tvaru, IPP bez uzlu UPS a uzel UPS s `System.CommunicationLost` rovným 1.
- Při chybě odešle agent na host serveru `vms.agent_status` 2 a `vms.agent_error` s popisem chyby podle UC5-R3, bez názvu turbíny; `ups.charge` v tomto cyklu neodešle.
- Chyba se zapíše do logovacího souboru podle UC5-R1.
- Po odstranění příčiny začne agent v nejbližším cyklu `ups.charge` znovu odesílat bez restartu služby.

### UC7-R4
**Popis:** Stav agenta na hostu serveru shrnuje čtení z databáze i z IPP a jedno neblokuje druhé.
**DoD:**
- `vms.agent_status` a `vms.agent_error` hostu serveru popisují čtení turbín z databáze i čtení serverových metrik z IPP podle UC5-R3.
- Chyba při čtení z IPP nezastaví odesílání metrik turbín.
- Nedostupná databáze nezastaví odesílání `ups.charge`.
- Chyby obou zdrojů v jednom cyklu se v textu `vms.agent_error` objeví společně.
- Nedostupnost Zabbix serveru se na host serveru nehlásí, stejně jako podle UC5-R3.

### UC7-R5
**Popis:** Balíček obsahuje samostatnou šablonu pro host serveru podle tabulek tohoto use casu.
**DoD:**
- Soubor šablony z UC3-R4 obsahuje vedle šablony turbín druhou šablonu „VMS zabbix agent server", která se naimportuje bez ruční úpravy souboru.
- Šablona serveru obsahuje právě metriky, triggery a makra z tabulek tohoto use casu, se stejnými pravidly jako v UC3-R4 a UC5-R4, a value map stavu agenta.
- Šablona turbín se přidáním šablony serveru nemění.

### UC7-R6
**Popis:** Šablona serveru hlásí chybu napájení, když nabití baterie klesne pod mez danou makrem.
**DoD:**
- Trigger Chyba napájení přejde do problémového stavu, když je poslední `ups.charge` menší než `{$VMS.UPS.CHARGE.MIN}`, tedy ve výchozím stavu pod 50 %.
- Nabití rovné mezi problém nehlásí.
- Makro jde přepsat na hostu serveru.

### UC7-R7
**Popis:** Dokumentace popisuje nasazení sledování UPS a chyby, které při něm agent hlásí.
**DoD:**
- Návod k nastavení Zabbixu popisuje založení hostu serveru, přiřazení šablony serveru a mez nabití `{$VMS.UPS.CHARGE.MIN}`.
- Návod říká, že host serveru je povinný i bez sledování UPS, protože nese stav agenta včetně chyb čtení z databáze.
- Návod popisuje, co obsluha nastaví ve skupině `server` konfigurace, aby agent začal UPS sledovat.
- Popis chyb agenta uvádí chyby podle UC7-R3 a kde k nim hledat podrobnosti.
