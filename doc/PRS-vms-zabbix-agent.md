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
