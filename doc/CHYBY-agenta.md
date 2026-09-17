# Chyby agenta

Přehled toho, co agent hlásí, kde chyby vznikají a kde k nim hledat podrobnosti.

## Kde se chyby projeví

| Kde | Co tam je |
| --- | --- |
| `vms.agent_status` v Zabbixu | 0 bez chyby, 1 varování, 2 chyba |
| `vms.agent_error` v Zabbixu | text poslední chyby nebo varování, **zkrácený na 255 znaků** |
| `C:\ProgramData\LogicElements\ZabbixVms\zabbixvms.log` | tentýž text v plném znění, s časem a úrovní |
| Windows Event Log, zdroj `ZabbixVms` | jen start a zastavení služby a chyby, které brání jejímu běhu |

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
- chyby `zabbix_utils` při odesílání: Zabbix server je nedostupný, odmítne spojení nebo
  vyprší časový limit

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
- `cannot read configuration ...` u poškozeného souboru

Tyhle chyby najdete v logu a v Event Logu. V Zabbixu se projeví jen nepřímo, triggerem
„Z hostu nepřišla žádná hodnota 5m“ — proto má tento trigger vyšší prioritu než hlášená
chyba: mlčící host může znamenat, že agent vůbec neběží.

Trigger má pevné okno 5 minut, kdežto prodleva mezi cykly se nastavuje v konfiguraci
(5 až 120 sekund). Při krátké prodlevě se do okna vejde mnoho cyklů, při prodlevě 120 s
už jen dva a půl — počítejte s tím, že při dlouhých prodlevách trigger reaguje citlivěji.

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
