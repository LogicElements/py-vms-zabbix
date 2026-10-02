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
    config.py            Config, ZabbixConfig, DatabaseConfig, Turbine, ServerConfig, UpsConfig
    log.py               logovací soubor s rotací a zápis do Windows Event Logu
    metrics.py           Metric, ValueType, METRICS, Trigger, TRIGGERS – katalogy turbín
                         a SERVER_METRICS, SERVER_TRIGGERS, SERVER_MACROS – katalogy serveru
    collector.py         Collector – čte BVMS a počítá hodnoty metrik
    ups.py               IppClient – čte nabití UPS z Eaton IPP
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
| `config.py` | načtení a uložení konfigurace, cesta do `ProgramData`, nasazení výchozí konfigurace z balíčku, kontrola rozsahů a prefixů surových dat, skupina `server` s přístupem k IPP, tabulka a okno trendových dat a jejich signály u turbíny, doplnění položek z novějších verzí v paměti i do souboru | UC2-R1 až UC2-R10, UC6-R1, UC7-R1, UC8-R1, UC8-R2 |
| `log.py` | logovací soubor vedle konfigurace, rotace, souběžný zápis služby i tray aplikace, zápis do Event Logu | UC5-R1, UC5-R2 |
| `metrics.py` | definice metrik: klíč, název, typ hodnoty, jednotka, popis; definice triggerů: název, klíč metriky, podmínka, priorita; zvlášť pro hosty turbín a pro host serveru | UC3-R1, UC3-R2, UC5-R4, UC7-R5 |
| `collector.py` | čtení řádku informační tabulky, počtů řádků bufferů, tabulek surových dat a okna trendových dat, výpočet hodnot | UC4-R1 až UC4-R5, UC4-R7, UC4-R8, UC6-R2 až UC6-R5, UC8-R3, UC8-R4 |
| `ups.py` | přihlášení k Eaton IPP, držení session, nejnižší nabití přes UPS, chyby čtení | UC7-R2, UC7-R3 |
| `sender.py` | odeslání hodnot trapperem pod hostem `<location>_<turbína>` nebo pod hostem serveru, kontrola odmítnutých hodnot | UC2-R2, UC2-R5, UC7-R2 |
| `agent.py` | cyklus přes turbíny a server, jeden společný stav agenta odesílaný na host serveru, prodleva mezi cykly, pokračování po chybě cyklu | UC1-R4, UC4-R6, UC5-R3, UC7-R3, UC7-R4 |
| `service.py` | registrace a odregistrace služby, automatický start, oprávnění k ovládání, příkaz `complete-config` pro aktualizaci | UC1-R2, UC1-R3, UC1-R7, UC2-R10 |
| `servicecontrol.py` | zjištění stavu služby a její spuštění, zastavení a restart | UC1-R5, UC1-R6 |
| `tray.py` | ikona podle stavu služby, kontextové menu včetně otevření datové složky | UC1-R5, UC1-R6, UC1-R8, UC2-R8 |
| `template.py` | šablony pro Zabbix vygenerované z katalogů metrik a triggerů, pro turbíny a pro server | UC3-R4, UC5-R4, UC7-R5 |

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

### Trendová data se čtou z okna posledních řádků

Čtvrtý dotaz (UC8) hledá, kdy se naposledy zapsal každý ze sledovaných signálů. Tabulka
trendových dat má miliony řádků a kromě primárního klíče `Id` nemá index, takže hledat
signál přes `SigID` by znamenalo projít celou tabulku, a to právě ve chvíli, kdy signál
přestal chodit a v tabulce už je jen hluboko. `Id` roste v pořadí zápisu, proto agent čte
jen okno posledních `trend_window` řádků:

```sql
SELECT SigID, MAX(PTimeStamp) FROM <tabulka>
WHERE Id > (SELECT MAX(Id) FROM <tabulka>) - <okno> AND SigID IN (...) GROUP BY SigID
```

`MAX(Id)` se čte z konce indexu a zbytek je rozsah primárního klíče (`type: range`,
`key: PRIMARY`), jeho cena tedy nezávisí na velikosti tabulky. Druhý dotaz čte `PTimeStamp`
prvního řádku okna. Signál, který v okně není, je starší, než kam okno dosahuje, a dostane
jeho stáří jako dolní mez; kdyby se jeho stáří hledalo dál, vrátila by se cena celé tabulky.
`PTimeStamp` je sloupec DATETIME, který konektor předá jako `datetime`. Přečte se i text
`yyyy-mm-dd HH:MM:SS`, kdyby ho někde tabulka držela jako text (lokální kopie ho tak
chvíli měla); hodnota, která čas není, se hlásí jako jeden měsíc.

Čas je druhá past. Zapisovací software razítkuje trvale časem UTC+1 a na letní čas nepřechází,
takže `PTimeStamp` je v létě o hodinu za hodinami serveru. Agent proto razítko bere jako čas
v pevném pásmu `trend_utc_offset` (výchozí 1) a `trend_timestamp()` ho převede na místní čas
serveru přes `astimezone()`, které letní čas zná. Přičíst konstantu nejde: v zimě, kdy je
místní čas UTC+1, by posunula stáří na druhou stranu a zastavený zápis by zůstal hodinu bez
povšimnutí. Razítko `0001-01-01`, kterým databáze říká „nikdy“, místní čas nemá; hlásí se jako
jeden měsíc. Pásmo místního času je v testech nahrazené proměnnou `LOCAL_ZONE`, aby výsledek
nezávisel na stroji, na kterém běží.

Dotazy sestavuje `trend_queries()` a plán jim ověřují databázové testy. Na tabulce s pěti
miliony řádků trvá čtení pod 100 ms (`ZABBIXVMS_SLOW_TESTS=1 pytest -m slow`). Lokální
`dukovany_local` zkopírovaná bez primárního klíče tenhle plán nemá a dotaz na ní prochází
tabulku celou.

### Nabití UPS se čte z webového rozhraní Eaton IPP

UPS na USB si zabírá ovladač Eatonu, takže ji Windows nevidí jako baterii a
`Win32_Battery` nic nevrací. SNMP by šlo jen na UPS se síťovou kartou. Zbývá IPP, který
UPS spravuje a USB i síťové připojení vystavuje stejně. Dokumentované rozhraní nemá, a tak
`ups.py` volá tytéž služby jako webová stránka IPP 1.73. Každá služba je POST formuláře na
`<url>/server/<služba>?action=<akce>` a odpovídá JSONem:

| Služba a akce | K čemu |
| --- | --- |
| `user_srv.js` `queryLoginChallenge` | výzva k přihlášení |
| `user_srv.js` `loginUser` | přihlášení, vrací `sessionID` |
| `data_srv.js` `getNodeData` | seznam zdrojů napájení (`System.Tag == PWS`) s jejich tagy |
| `data_srv.js` `loadNodeData` | aktuální hodnoty vybraných uzlů |

Heslo se posílá jako HMAC-SHA1 přes výzvu s klíčem SHA1 hesla v šestnáctkovém zápisu,
stejně jako v `user_settings.js` stránky. IPP počítá SHA1 vlastní funkcí v JavaScriptu, která
čte znaky textu, ne jeho bajty. Se standardním SHA1 se proto shoduje jen pro ASCII, což
ověřilo spuštění jeho `libs/utils.js` pod Windows Script Host. Konfigurace s heslem mimo ASCII
se odmítne.

Za UPS se považuje uzel, který má mezi tagy `UPS`. Nabitím je
`UPS.PowerSummary.RemainingCapacity`, a když IPP spravuje víc UPS, hlásí se ta, která je na
tom nejhůř. `loadNodeMeasures` se nepoužívá, protože vrací jen historii změn a u nabití, které
se nemění, je prázdný.

Po přihlášení se `sessionID` posílá ve formuláři i v cookie `sessionID`, stejně jako to dělá
stránka. Bez cookie IPP datové služby neobslouží a zavře spojení, aniž by odpověděl. Tak se
to projevilo na serveru: přihlášení prošlo a hned první `getNodeData` skončil hláškou
`Remote end closed connection without response`. HAR z Edge cookie nezachytil, protože je
novější Edge při exportu vynechává.

Session se drží mezi cykly. Zavřené spojení bez odpovědi je způsob, jakým IPP odmítá dotaz
bez platné session. Vypršelou session nejspíš odmítá stejně, zaznamenat se to ale nepodařilo.
Proto každé selhání čtení nad starou session vede k jednomu novému přihlášení a opakování
čtení ve stejném cyklu, i když IPP spojení jen zavřel. Výjimky jsou dvě. Při
`System.CommunicationLost` ztratil IPP spojení s UPS a session za to nemůže. IPP, který
vůbec neodpovídá, tedy odmítne spojení nebo nestihne odpovědět včas, by nové přihlášení jen
znovu nechalo čekat.

IPP má vlastní certifikát podepsaný sám sebou a běží na tomtéž serveru, takže se certifikát
neověřuje. Ze stejného důvodu jdou dotazy mimo proxy nastavenou pro stroj, ať už
v proměnných prostředí nebo v registru. Adresy se zkoušejí v pořadí IPv4 před IPv6. IPP
poslouchá jen na `0.0.0.0`, kdežto Windows na serveru vrací pro `localhost` jako první `::1`.
Odmítnuté spojení na `::1` trvá Windows 2 sekundy, a to se na serveru platilo u každého
dotazu. Cyklus se čtyřmi dotazy tak trval 8 sekund. Jeden dotaz smí trvat nejvýš 10 sekund. Protože se
agent k neodpovídajícímu IPP znovu nepřihlašuje, zdrží zaseknutý IPP cyklus turbín nejvýš
o těchto 10 sekund.

Testy běží proti falešnému IPP. Odpovědi datových služeb jsou ty, které IPP 1.73 poslal
prohlížeči, uložené v `tests/data/ipp`. Odpovědi přihlášení zaznamenané nejsou, jejich tvar
vychází z toho, co z nich čte `user_settings.js`.

### Turbíny a server jsou dvě nezávislé části cyklu

Stav agenta je jeden a hlásí se jen na host serveru. Cyklus v `agent.py` má dvě části,
turbíny a server, a chyba jedné nezastaví druhou; obě vrátí svůj stav a text a `run()` z nich
složí stav cyklu: nejhorší status a texty spojené středníkem. Text chyby turbíny začíná
jejím názvem, k čemuž si agent pamatuje, u které turbíny cyklus skončil (`_turbine_in_work`);
chyba bez turbíny (připojení k databázi, IPP) název nemá. Nedostupný Zabbix se počítá jednou
za cyklus bez ohledu na to, kolik hostů se nedovolalo, a stav se pak neodesílá. Log o něm
přijde po pěti cyklech stejně jako dřív.

Katalogy metrik a triggerů jsou dva a šablony v `zabbix_template.yaml` také. Stav agenta
a value map má jen šablona serveru, šablona turbín na ticho hlídá `nodata` nad `vms.speed`.
Šablona serveru má UUID odvozená s předponou `server:`, aby se s šablonou turbín nikdy
nepotkala. Šablona turbín si ponechává UUID, se kterými byla exportovaná poprvé, takže nový
import ji aktualizuje na místě.
