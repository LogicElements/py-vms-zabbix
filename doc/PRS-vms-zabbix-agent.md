# Product Requirement Specification (PRS)

## Přehled requirementů

| Requirement | Popis | Stav |
| --- | --- | --- |
| UC1-R1 | Implementace v Pythonu, jeden balíček se službou i tray aplikací | Zbývá |
| UC1-R2 | Registrace a ovládání jako služba Windows `ZabbixVms` | Zbývá |
| UC1-R3 | Automatický start se systémem bez přihlášení uživatele | Zbývá |
| UC1-R4 | Nepřetržitý běh, chyba jednoho cyklu službu neukončí | Zbývá |
| UC1-R5 | Ikona v systray signalizující barvou stav služby | Zbývá |
| UC1-R6 | Spuštění, zastavení a restart služby z kontextového menu ikony | Zbývá |
| UC1-R7 | Ovládání služby i běžným uživatelem, povolené přes ACL služby | Zbývá |
| UC1-R8 | Automatické spuštění tray aplikace při přihlášení uživatele | Zbývá |
| UC2-R1 | Konfigurace jako JSON dump konfigurační třídy přes jsonpickle | Zbývá |
| UC2-R2 | Skupina parametrů odesílání do Zabbixu: spojení a `location` | Zbývá |
| UC2-R3 | Seznam 1 až 4 turbín, každá nastavená samostatně | Zbývá |
| UC2-R4 | Agent konfiguraci při svém běhu nepřepisuje | Zbývá |
| UC2-R5 | Turbína popsaná názvem, system_id a jedním až dvěma buffery | Zbývá |
| UC2-R6 | Skupina parametrů databáze MySQL: spojení a tabulka `info` | Zbývá |
| UC2-R7 | Aktivní konfigurace v ProgramData, v balíčku jen výchozí šablona | Zbývá |
| UC2-R8 | Otevření konfigurace k editaci z kontextového menu ikony | Zbývá |
| UC3-R1 | Sada odesílaných metrik vedená jako tabulka v PRS | Zbývá |
| UC3-R2 | Sloupce tabulky dostačují k založení položky v Zabbixu | Zbývá |
| UC3-R3 | Metriky bufferů podle počtu nastavených bufferů turbíny | Zbývá |
| UC3-R4 | Šablona pro Zabbix v balíčku a stručný návod k jejímu nasazení v `doc/` | Zbývá |

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
- Balíček se nainstaluje příkazem `pip install .` na Windows serveru s Pythonem 3.7 nebo novějším.
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
- Seznam bufferů obsahuje jeden nebo dva buffery; konfiguraci s prázdným seznamem nebo s více než dvěma buffery agent odmítne jako neplatnou.
- Turbína s jedním nastaveným bufferem je platná a agent u ní druhý buffer nevyžaduje.
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
- Kontextové menu ikony obsahuje položku Open configuration.
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
| `vms.info_age` | Stáří info záznamu | Numeric (unsigned) | s | |
| `vms.timestamp_age` | Stáří časové značky | Numeric (unsigned) | s | |
| `vms.config_age` | Stáří konfigurace | Numeric (unsigned) | s | |
| `vms.buf_rows_1` | Počet řádků v bufferu 1 | Numeric (unsigned) | | Počet řádků v první bufferové tabulce |
| `vms.buf_rows_2` | Počet řádků v bufferu 2 | Numeric (unsigned) | | Počet řádků v druhé bufferové tabulce |
| `vms.buf_age_1` | Stáří bufferu 1 | Numeric (unsigned) | s | Doba od poslední změny první bufferové tabulky |
| `vms.buf_age_2` | Stáří bufferu 2 | Numeric (unsigned) | s | Doba od poslední změny druhé bufferové tabulky |
| `vms.buf_bulk_1` | Bulk bufferu 1 | Numeric (unsigned) | | |
| `vms.buf_bulk_2` | Bulk bufferu 2 | Numeric (unsigned) | | |

Popis u části metrik se doplní později; v Zabbixu je nepovinný.

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
**Popis:** Metriky vázané na buffer se odesílají pro každý buffer nastavený u dané turbíny.
**DoD:**
- U turbíny se dvěma nastavenými buffery se odesílají metriky obou bufferů.
- U turbíny s jedním nastaveným bufferem se odesílají metriky pouze tohoto bufferu.
- Klíč metriky rozlišuje, ke kterému z bufferů turbíny hodnota patří.

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
