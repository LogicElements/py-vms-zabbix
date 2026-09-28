# Chyby agenta

Přehled toho, co agent hlásí, kde chyby vznikají a kde k nim hledat podrobnosti.

## Kde se chyby projeví

| Kde | Co tam je |
| --- | --- |
| `vms.agent_status` v Zabbixu | 0 bez chyby, 1 varování, 2 chyba |
| `vms.agent_error` v Zabbixu | text poslední chyby nebo varování, **zkrácený na 255 znaků** |
| host serveru v Zabbixu | vlastní `vms.agent_status` a `vms.agent_error`, jen o čtení nabití UPS z IPP |
| `C:\ProgramData\LogicElements\ZabbixVms\zabbixvms.log` | tentýž text v plném znění, s časem a úrovní |
| Windows Event Log, zdroj `ZabbixVms` | jen start a zastavení služby a chyby, které brání jejímu běhu |

Ke složce s logem se nejrychleji dostanete z kontextového menu ikony v systray položkou
**Otevřít datovou složku**; leží v ní log i konfigurace.

Log je vždy úplnější zdroj než `vms.agent_error`: není zkrácený a drží i historii, ne
jen poslední událost.

## Úplný výčet chyb neexistuje

Do `vms.agent_error` jde text výjimky, která shodila cyklus měření. Část textů pochází
z našeho kódu a je vypsaná níže, ale část prochází beze změny z knihoven
`mysql-connector-python` a `zabbix_utils` — tam uvidíte hlášku MySQL serveru nebo síťové
vrstvy slovo od slova. Následující seznam je proto výčtem **kategorií**, ne všech možných
textů.

## Stav 2 — chyba

Agent se nedostal k hodnotám nebo je nedokázal odeslat. Cyklus skončil, smyčka ale běží
dál a další cyklus to zkusí znovu.

**Z kódu agenta:**

- `table info_le has no row with SystemId 10 of turbine 'TEST'`
  Turbína má v konfiguraci `system_id`, ke kterému v informační tabulce není řádek.
  Typicky překlep v `system_id` nebo turbína, která do databáze ještě nic nezapsala.
- `Zabbix rejected 10 of 10 values of host LE_TEST`
  Trapper hodnoty nepřijal. Nejčastější příčina je, že host toho jména v Zabbixu není —
  jméno musí přesně odpovídat tvaru `<location>_<název turbíny>` z konfigurace.
- `collector is not connected to the database`
  Vnitřní stav, který by za běhu nastat neměl.

**Prochází z knihoven:**

- chyby `mysql-connector-python` při připojení nebo dotazu: MySQL neběží, špatné
  uživatelské jméno či heslo, neexistující databáze nebo informační tabulka, síť
- chyby `zabbix_utils` při odesílání, které nejsou o dostupnosti serveru: nečitelná
  odpověď trapperu nebo selhání při vytváření socketu

**Na hostu serveru, při čtení UPS z IPP:**

Tyhle chyby vidí jen host serveru. Hosty turbín hlásí dál jen to, co se týká databáze, a na
hostu serveru se naopak neobjeví nic o MySQL. V cyklu s chybou agent nabití `ups.charge`
neodešle. Jakmile příčina zmizí, nabití v dalším cyklu zase přijde, bez restartu služby.

- `IPP at https://localhost:4680 cannot be reached: ...`
  Na adrese z `server.ups.url` nikdo neodpovídá, nebo neodpověděl do 10 sekund. Typicky
  neběží služba IPP nebo je v konfiguraci špatná adresa či port. Za dvojtečkou je důvod
  od síťové vrstvy, například odmítnuté spojení nebo vypršený čas.
- `IPP turned down the login of user 'admin'`
  Špatné `login` nebo `password` ve skupině `server.ups`. Údaje ověříte přihlášením do
  webového rozhraní IPP.
- `IPP manages no UPS`
  IPP běží a přihlášení prošlo, ale mezi zdroji napájení nemá žádnou UPS. Typicky UPS
  v IPP ještě není přidaná nebo ji IPP po výměně nenašel.
- `IPP lost the communication with UPS GA10R14030`
  IPP o UPS ví, ale ztratil s ní spojení, například kvůli odpojenému kabelu USB nebo
  výpadku síťové karty UPS. Za UPS je její sériové číslo z IPP. Nabití, které IPP drží,
  je poslední známé, ne aktuální, proto se neposílá.
- `IPP answered getNodeData with HTTP 500`, `IPP answered loadNodeData with something else
  than JSON`, `IPP gave UPS ... no number in UPS.PowerSummary.RemainingCapacity` a podobné
  IPP odpověděl jinak, než jak odpovídá verze 1.73, podle které agent vznikl. Nejčastěji
  jde o jinou verzi IPP. Podrobnosti najdete v logu.
- `Zabbix rejected 1 of 1 values of host LE_server`
  Host serveru toho jména v Zabbixu není. Jméno musí přesně odpovídat `server.host`
  z konfigurace.

Kvůli vypršelé session se agent k IPP jednou za cyklus přihlásí znovu a čtení zopakuje.
Chyba se hlásí, teprve když selže i to.

## Stav 1 — varování

Cyklus proběhl celý, ale něco stojí za pozornost.

- `buffer table 'buffer_le_3' of turbine 'TEST' is not in database BVMS`
  Turbína má v konfiguraci bufferovou tabulku, která v databázi není. Metrika počtu řádků
  by za ni hlásila nulu, což vypadá jako prázdný buffer — a to je něco jiného než tabulka,
  která vůbec neexistuje.

## Co se do Zabbixu nedostane

Neplatnou konfiguraci agent pozná při startu služby a **službu nespustí**, takže žádnou
metriku odeslat nemůže:

- `configuration has 5 turbines, 1 to 4 are supported`
- `turbine 'TEST' has 3 buffers, at most 2 are supported`
- `turbine 'TEST' has raw data prefix 'btt-tg1', only letters, digits and underscores are allowed`
- `C:\ProgramData\LogicElements\ZabbixVms\config.json lacks turbines[0].system_id`
  Konfiguraci chybí položka, za kterou agent výchozí hodnotu nedosadí, protože by četl
  jinou turbínu nebo posílal pod jiného hosta. Výchozí hodnotu dostanou jen položky, které
  přibyly v novější verzi agenta; ty si doplní sám.
- `cannot read configuration ...` u poškozeného souboru, například s chybou v zápisu JSON
- `server.host is empty, the UPS is watched only with a Zabbix host of the server to send it to`
  Sledování UPS je zapnuté, ale chybí jméno hostu serveru.
- `server.ups.password may hold ASCII characters only, IPP cannot take any other`
  IPP heslo s diakritikou od agenta nepřijme, viz [návod na Zabbix](NAVOD-zabbix.md),
  kapitola 7.
- `server.ups.enabled is 'false', true or false is expected`
  Hodnota zapnutí UPS je v uvozovkách. Musí to být `true` nebo `false` bez uvozovek.

Tyhle chyby najdete v logu a v Event Logu. V Zabbixu se projeví jen nepřímo, triggerem
„Z hostu nepřišla žádná hodnota 5m“ — proto má tento trigger vyšší prioritu než hlášená
chyba: mlčící host může znamenat, že agent vůbec neběží.

Trigger má pevné okno 5 minut, kdežto prodleva mezi cykly se nastavuje v konfiguraci
(5 až 120 sekund). Při krátké prodlevě se do okna vejde mnoho cyklů, při prodlevě 120 s
už jen dva a půl — počítejte s tím, že při dlouhých prodlevách trigger reaguje citlivěji.

### Nedostupný Zabbix

Když se agent na Zabbix vůbec nedovolá – server neběží, odmítne spojení nebo vyprší časový
limit – **nehlásí to jako chybu agenta**. Nemá totiž kudy: hlášení by odešlo až po obnovení
spojení a popisovalo by výpadek, který už skončil. Cyklus se přejde a zkusí se znovu za
periodu.

Po pěti takových cyklech za sebou se do logu zapíše jeden záznam a další přibude, až se
odesílání zase rozběhne, takže je z logu vidět i to, jak dlouho výpadek trval. V Zabbixu se
delší výpadek projeví triggerem „Z hostu nepřišla žádná hodnota 5m“; krátké zaškobrtnutí se
v něm neprojeví vůbec, což je záměr.

### Stojící turbína není chyba

Triggery nad stářím zápisu do bufferu (`vms.buf_age`) a do tabulek surových dat
(`vms.raw_write_age`) mlčí, dokud jsou otáčky pod mezí makra `{$VMS.SPEED.NOMINAL}`. Stojící
turbína do nich nic neukládá, takže rostoucí stáří je v takové chvíli očekávané. Ostatní
triggery podmíněné nejsou – zbylé zdroje se plní bez ohledu na otáčky. Řeší to
závislost na triggeru *Turbína pod nominálními otáčkami*, viz
[návod na Zabbix](NAVOD-zabbix.md). Agent sám v tom nehraje roli – posílá metriky stejně
jako jindy, rozhoduje se až v Zabbixu.

### Chybějící tabulka surových dat není chyba agenta

Když k prefixu z `raw_prefixes` v databázi žádná tabulka není, agent to nehlásí jako
varování. Je to totiž přesně ta porucha, kterou mají metriky surových dat ukázat: stáří zápisu
se hlásí jako jeden měsíc a v Zabbixu se ozve *Chyba zápisu surových dat*. Stejně se ale
projeví i překlep v prefixu – u chyby hned po nasazení proto nejdřív porovnejte prefixy
v konfiguraci s názvy tabulek v databázi.

### Pád procesu na nativní úrovni

Chybu uvnitř nativní knihovny (`.pyd`, `.dll`) už Python zachytit nedokáže — proces
zanikne okamžitě a v souborovém logu ani ve vlastním Event Logu agenta po něm nezůstane
nic. Jedinou stopou je záznam **Application Error** v Event Logu Windows, kde je uvedený
`pythonservice.exe` a padající modul.

Jeden takový případ je známý. Konektor k MySQL s sebou nese `libmysql.dll` přeloženou
novějším Visual Studiem, jehož `std::mutex` potřebuje běhové prostředí Visual C++ verze
14.40 nebo novější. Proti staršímu zůstane zámek neinicializovaný a knihovna spadne
s výjimkou `0xC0000005` v modulu `MSVCP140.dll`. Agent se tomu vyhýbá tím, že do MySQL
chodí přes čistě Pythonovou implementaci konektoru (`use_pure=True`), takže do
`libmysql.dll` vůbec nevstoupí. Verzi běhového prostředí na serveru zjistíte příkazem:

```powershell
(Get-Item C:\Windows\System32\msvcp140.dll).VersionInfo.FileVersion
```

V Zabbixu se takový pád projeví stejně jako neběžící služba, tedy triggerem
„Z hostu nepřišla žádná hodnota 5m“.
