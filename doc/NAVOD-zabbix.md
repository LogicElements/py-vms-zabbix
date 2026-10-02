# Nastavení Zabbixu

Návod k nasazení šablon agenta. Nejprve se naimportuje šablona, pak se založí hosté;
kroky 1 a 3 se opakují pro každou turbínu z konfigurace. Host serveru, který nese stav
agenta a nabití UPS, popisuje kapitola 7 a je potřeba na každé instalaci. Po aktualizaci
agenta na novou verzi stačí šablonu naimportovat znovu, nové položky a triggery se tím
doplní ke stávajícím; položky a triggery, které nová verze zrušila, odstraní volba
**Delete missing** v dialogu importu, viz kapitola 2.

## 1. Založit hosta

Pro každou turbínu založte v Zabbixu hosta se jménem ve tvaru
`<location>_<název turbíny>`, tedy hodnota `location` ze skupiny `zabbix` v konfiguraci
a název turbíny spojené podtržítkem. Při `location` `Praha` a turbíně `TG1` je jméno
hosta `Praha_TG1`.

Zabbix u hosta vyžaduje i **Host groups**. Zvolte skupinu `VMS`; pokud ještě neexistuje,
napište její název do toho pole a Zabbix ji založí. Nepoužívejte `Templates/Applications`,
to je skupina šablon, ne hostů.

## 2. Naimportovat šablonu

V Zabbixu zvolte **Data collection → Templates → Import** a vyberte soubor
`zabbix_template.yaml` ze složky `data` nainstalovaného balíčku. Cestu k němu vypíše:

```bash
python -c "from zabbixvms.template import template_path; print(template_path())"
```

Soubor nese dvě šablony: **VMS zabbix agent** pro hosty turbín a **VMS zabbix agent
server** pro host serveru z kapitoly 7. Import založí obě najednou.

Při importu nové verze nad starou zaškrtněte v dialogu u **Items**, **Triggers** a
**Value mappings** volbu **Delete missing**. Od verze 0.4.0 šablona turbín nemá položky
*Stav agenta* a *Poslední chyba agenta*, jejich triggery ani value map; bez této volby by
na hostech turbín zůstaly staré, které už nedostávají žádnou hodnotu, a trigger na ně by
hlásil ticho.

## 3. Přiřadit šablonu hostovi

V nastavení každého založeného hosta přidejte do pole **Templates** šablonu
**VMS zabbix agent** a změnu uložte. Tím na hostovi vzniknou položky pro všechny
metriky turbíny i triggery hlásící její poruchy. Když z hosta turbíny přestanou chodit
otáčky (`vms.speed`) na 5 minut, ozve se trigger *Z hostu nepřišla žádná hodnota 5m*.
Pokrývá neběžícího agenta, nečitelnou databázi i nedostupný Zabbix; důvod ale hledejte
ve stavu agenta na hostu serveru (kapitola 7).

Pole **Templates** je součástí formuláře hosta, takže je šablona po kroku 2 k dispozici
a jde vyplnit rovnou při zakládání hosta v kroku 1.

## 4. Mez otáček, pokud turbína nejede na 3000

Šablona nese makro `{$VMS.SPEED.NOMINAL}` s výchozí hodnotou **2500**. Pod touhle mezí se
turbína považuje za neběžící a trigger *Turbína pod nominálními otáčkami* přejde do
problémového stavu.

Ten trigger sám o sobě nic nehlásí jako poruchu – jeho smyslem je **umlčet triggery nad
stářím zápisu do bufferu** (`vms.buf_age`), **do tabulek surových dat**
(`vms.raw_write_age`) **a trendových dat** (`vms.trend_age`). Stojící turbína do nich nic
neukládá, takže by jinak jejich stářím poplašila dohled pokaždé, když se zastaví. Všechny
tři triggery na něm mají závislost, takže se po dobu jeho aktivity neuplatní.

Jakmile zapnete odesílání e-mailů podle kapitoly 5, má to ale jeden důsledek: priorita
Average dostane tenhle trigger nad prahovou hodnotu, takže při každém zastavení turbíny
přijde mail. Je to záměr, ne chyba nastavení; když to u některé turbíny vadí, jde ji
z rozesílání vyjmout podle 5.4.

Ostatní triggery hlásí bez ohledu na otáčky: databáze VMS setupu i oba sockety se plní
i za klidu, přeplněný buffer je problém taky a tabulky surových dat se za klidu nehromadí,
protože nové nevznikají. Kdyby se ukázalo, že další trigger má za klidu mlčet, přidá se mu
stejná závislost.

Turbína s jinými nominálními otáčkami nepotřebuje vlastní šablonu, stačí makro přepsat
u hosta: v nastavení hosta záložka **Macros → Inherited and host macros**, u
`{$VMS.SPEED.NOMINAL}` zvolit **Change** a zadat vlastní hodnotu. Ostatní hosté dál jedou
podle šablony.

## 5. E-mail při problému od priority Average výš

Tahle kapitola se dělá jednou pro celou instalaci, ne pro každou turbínu. Musí si sednout
tři objekty a **každý z nich má vlastní vypínač**: způsob odesílání pošty, adresa
u uživatele a pravidlo, kdy se má mail poslat. Když jeden z nich nesedí, Zabbix nikde
nehlásí chybu – jen nic nepřijde.

### 5.1 Nastavit odesílání pošty

**Alerts → Media types → Email**. V čerstvé instalaci je tenhle media type **zakázaný**
a vyplněný ukázkovými hodnotami (`mail.example.com`, `zabbix@example.com`), takže se bez
úpravy nikam nedovolá.

Vyplňte adresu a port SMTP serveru, adresu odesílatele, zabezpečení spojení
(None / STARTTLS / SSL/TLS) a případné přihlášení. Pozor na adresu odesílatele – relay
často odmítne poštu od odesílatele, kterého nezná. Nakonec media type **povolte**
a v seznamu zkontrolujte, že má stav Enabled.

Na záložce **Message templates** musí být řádek pro **Problem**, protože z něj se bere text
zprávy. Standardní Email ho má předvyplněný, takže jde spíš o kontrolu než o práci.

### 5.2 Dát uživateli adresu a přístup k hostům

Nejdřív oprávnění, protože tohle je ta nejtišší past: **uživatel dostane notifikaci jen
k hostům, na které má aspoň právo Read**, a práva se přidělují přes skupinu uživatelů,
nikdy přímo u uživatele. Ve skupině, do které příjemce patří, tedy dejte skupině hostů
`VMS` z kapitoly 1 oprávnění **Read**. Účet typu Super admin vidí všechno, takže zkouška
pod ním o běžném účtu nic nedokazuje.

Pak teprve adresa: **Users → Users → <uživatel>**, záložka **Media**, přidat médium typu
`Email` s adresou příjemce. Časové okno nechte na `1-7,00:00-24:00` a výběr závažností
nechte celý zaškrtnutý – prahovou hodnotu řeší pravidlo v 5.3. Médium se uloží teprve
uložením celého uživatele, samotné přidání do seznamu nestačí.

### 5.3 Říct, kdy se má mail poslat

**Alerts → Actions → Trigger actions**. Výchozí akci *Report problem to Zabbix
administrators* nechte být: je zakázaná a není omezená na skupinu `VMS`, takže by po
povolení rozesílala i věci, které s turbínami nesouvisejí. Založte vlastní.

V podmínkách nastavte dvě věci: závažnost **>= Average** a skupinu hostů `VMS`. Podmínky
různých typů se spojují logickým A, takže mail půjde jen z problémů téhle šablony a jen od
priority Average výš. V operacích přidejte odeslání zprávy uživatelské skupině přes médium
`Email`; vlastní text nevyplňujte, ať se použije šablona zprávy z 5.1. Vyplatí se přidat
i operaci při vyřešení problému, jinak schránka ukazuje jen vznik problémů a nikdy jejich
konec. Akci nakonec povolte.

Prahová hodnota patří do podmínky akce, ne k jednotlivým uživatelům. Akce je jedna a mění
se na jednom místě, kdežto výběr závažností u uživatele je jen druhá branka, která umí
ubrat, ne přidat. Nově založený uživatel má navíc zaškrtnuté všechny závažnosti, takže
kdyby byla mez jen tam, dostával by i Warning a Information.

### 5.4 Vypnout maily jednomu hostu

Testovací turbína může zůstat ve skupině `VMS` a přesto nemailovat. Hostu přidejte tag,
třeba `mail` s hodnotou `off`, a akci z 5.3 dejte podmínku navíc: hodnota tagu `mail`
**není rovna** `off`. Zapínání a vypínání je pak jen přidání nebo odebrání tagu u hosta,
akci už nikdy neupravujete a funguje to na libovolný počet hostů. Události nesou kromě
tagů triggeru i tagy hosta, takže na ně podmínka dosáhne.

Na krátkodobé ztišení se hodí spíš údržbové okno (**Data collection → Maintenance**)
s volbou *With data collection*: metriky dál tečou a problémy jsou v přehledu vidět, jen
se k nim nerozesílá pošta, protože akce má potlačené problémy ve výchozím stavu
pozastavené.

Pro jednoho dva hosty jde do akce dát rovnou podmínku, že host není `LE_TEST`. Je to
nejrychlejší cesta, ale při každém dalším hostu se akce musí znovu upravit.

## 6. Surová data VMS a TVMS

Tabulky surových dat se v Zabbixu nenastavují, šablona na ně má položky i triggery hotové.
Které tabulky patří ke které turbíně, se nastavuje v konfiguraci agenta: turbína má seznam
`raw_prefixes` a v něm prefixy tabulek surových dat VMS i TVMS, které k ní patří. Tabulka
patří k prefixu, když se jmenuje `<prefix>_<datum>`, u VMS s datem `yyyymmddHHMMSS`, u TVMS
`yyyymmdd`.

| Turbína | `raw_prefixes` |
| --- | --- |
| EDU TG11 | `["btt_tg11", "tg11_out"]` |
| EDU TG31 | `["btt_tg31", "tvms_tg31"]` |
| ETE TG1 | `["btt_tg1"]` |
| ETE TG2 | `["btt_tg2a", "btt_tg2b", "btt_tg2c"]` |

Turbína bez surových dat má seznam prázdný a hlásí u obou metrik nulu. Změna seznamu se
projeví po restartu služby.

Šablona k tomu hlásí dvě chyby:

- *Chyba exportu surových dat*, když má jeden prefix v databázi 3 a více tabulek: vzniká nová
  tabulka, ale ty staré se neexportují a nemažou.
- *Chyba zápisu surových dat*, když se do nejnovější tabulky některého prefixu 5 minut nic
  nezapsalo. Za klidu turbíny mlčí, viz kapitola 4. Na první zápis do nově založené tabulky
  čeká agent minutu; zůstane-li tabulka i potom prázdná, hlásí stáří zápisu jeden měsíc
  a chyba se ozve hned.

Překlep v prefixu vypadá stejně jako software, který vůbec neběží: prefix nemá žádnou tabulku
a stáří zápisu se hlásí jako jeden měsíc. Když chyba zápisu přijde hned po nasazení, porovnejte
nejdřív prefixy s názvy tabulek v databázi.

## 6a. Trendová data

Trendová data se zapisují do jedné tabulky databáze pro celého agenta, i když sleduje víc
turbín. Agent hlídá, jak staré jsou poslední záznamy vybraných signálů, a do Zabbixu
posílá jedinou metriku *Stáří trendových dat* (`vms.trend_age`): stáří toho signálu, který
je nejstarší. Šablona na ni má položku i trigger *Chyba trendových dat*, který se ozve, když
je stáří přes 5 minut. Za klidu turbíny mlčí, viz kapitola 4.

V Zabbixu se nic nenastavuje, signály se nastavují v konfiguraci agenta:

| Položka | Kde | Význam | Výchozí |
| --- | --- | --- | --- |
| `trend_table` | `database` | tabulka trendových dat, jedna pro celého agenta | `dukovany_local` |
| `trend_window` | `database` | počet nejnovějších řádků tabulky, ve kterých se signály hledají (1000 až 1000000) | 10000 |
| `trend_utc_offset` | `database` | o kolik hodin je `PTimeStamp` před UTC, pevně po celý rok; `null` = čas serveru | 1 |
| `trend_signals` | u turbíny | seznam `SigID` sledovaných signálů | `[]` |

```json
"trend_signals": [-4058, -4060, -4071, -4072, -4075, -4083]
```

Signály jednotlivých turbín podle stavu k 2026-10-01. U každé turbíny jsou tři signály: VMS,
TVMS a TEMP (u ETE jen VMS), a tabulka trendových dat se nastavuje podle serveru, na kterém
agent běží. Čísla v `trend_signals` jsou `SigID`, signály ve sloupci vedle nich jsou ve stejném pořadí.

| Server | `trend_table` | Turbína | `trend_signals` | Signály v tomto pořadí |
| --- | --- | --- | --- | --- |
| EDU RB1 | `dukovany_local` | TG11 | `[-4058, -4071, -4075]` | VMS, TVMS, TEMP |
| EDU RB1 | `dukovany_local` | TG12 | `[-4060, -4072, -4083]` | VMS, TVMS, TEMP |
| EDU RB2 | `dukovany_local` | TG21 | `[-26016, -26024, -26026]` | VMS, TVMS, TEMP |
| EDU RB2 | `dukovany_local` | TG22 | `[-27016, -27024, -27026]` | VMS, TVMS, TEMP |
| EDU RB3 | `dukovany_local` | TG31 | `[-28016, -28024, -28026]` | VMS, TVMS, TEMP |
| EDU RB3 | `dukovany_local` | TG32 | `[-29016, -29024, -29026]` | VMS, TVMS, TEMP |
| EDU RB4 | `dukovany_local` | TG41 | `[-30016, -30024, -30026]` | VMS, TVMS, TEMP |
| EDU RB4 | `dukovany_local` | TG42 | `[-31016, -31024, -31026]` | VMS, TVMS, TEMP |
| ETE TG1 | `tg1_local` | TG1 | `[-34002]` | VMS |
| ETE TG2 | `tg2_local` | TG2 | `[202795, 202814, 202833]` | VMS A, VMS B, VMS C |

Kontrolují se všechny signály ze seznamu a odesílá se stáří nejstaršího z nich. Turbína
s prázdným seznamem metriku vůbec neposílá. Změna se projeví po restartu služby.

**Čas v tabulce a letní čas.** Software, který trendová data zapisuje, razítkuje `PTimeStamp`
trvale časem UTC+1 a na letní čas nepřechází. V létě je razítko o hodinu za hodinami serveru,
v zimě s nimi souhlasí. Bez `trend_utc_offset` by agent v létě hlásil u čerstvě zapisovaného
signálu stáří přes hodinu. Hodnota 1 platí pro tabulky zapisované tímto softwarem. Nastavuje
se na pevný posun, ne na hodinu navíc: agent razítko převede na místní čas serveru a letní čas
se tím vyřeší sám. Přičíst konstantu by v zimě posunulo stáří na druhou stranu a zastavený
zápis by zůstal hodinu bez povšimnutí. Má-li některá tabulka razítka v čase serveru, nastavte
`"trend_utc_offset": null`.

**Okno musí pokrýt víc než 5 minut zápisu.** Tabulka má miliony řádků a signál, který
přestal chodit, by se hledal přes všechny. Agent proto čte jen posledních `trend_window`
řádků podle primárního klíče `Id`. Signál, který v okně není, dostane stáří začátku okna,
tedy dolní mez skutečného stáří; trigger se ozve správně, jen když okno sahá dál než 5 minut.
Při zápisu asi 6 řádků za sekundu stačí výchozích 10000 řádků na zhruba 26 minut. Zapisuje-li
se do tabulky rychleji, okno zvětšete. Hodnotu stáří pak čtěte jako „nejméně“.

Dotaz počítá s tím, že `Id` je primární klíč tabulky. Lokální pracovní kopie `dukovany_local`
ho mít nemusí, pak je dotaz na ní pomalý; `ALTER TABLE dukovany_local ADD PRIMARY KEY (Id)`.

## 7. Host serveru: stav agenta a nabití UPS

Na host serveru posílá agent **stav agenta** a nabití baterie UPS. Stav agenta (*Stav
agenta* a *Poslední chyba agenta*) popisuje celý cyklus měření, tedy čtení z databáze
i z IPP, a na hosty turbín se neposílá. Host serveru je proto potřeba na každé instalaci,
i když se UPS nesleduje. Na host přibudou později i další metriky společné celému
serveru. Kapitola se dělá jednou za server.

Nabití baterie UPS čte agent z Eaton Intelligent Power Protector (IPP), který na serveru
UPS spravuje. Na způsobu připojení UPS k IPP nezáleží, USB i síť se čtou stejně.

### 7.1 Nastavit skupinu `server` v konfiguraci agenta

V `C:\ProgramData\LogicElements\ZabbixVms\config.json` vyplňte skupinu `server`:

```json
"server": {
  "py/object": "zabbixvms.config.ServerConfig",
  "host": "LE_server",
  "ups": {
    "py/object": "zabbixvms.config.UpsConfig",
    "enabled": true,
    "url": "https://localhost:4680",
    "login": "admin",
    "password": "heslo do IPP"
  }
}
```

- `host` je celé jméno hostu serveru v Zabbixu. Na rozdíl od turbín se neskládá
  z `location`, takže se píše celé. Je povinné vždy, i s vypnutým UPS: bez něj by stav
  agenta neměl kam jít a agent konfiguraci odmítne.
- `url` je adresa webového rozhraní IPP. Výchozí `https://localhost:4680` platí, když IPP
  běží na tomtéž serveru. Adresa `http://…:4679` jen přesměrovává sem.
- `login` a `password` jsou údaje, se kterými se přihlašujete do webového rozhraní IPP.
  Heslo smí obsahovat jen znaky ASCII, tedy bez diakritiky. Jiné heslo IPP od agenta
  nepřijme a agent je proto odmítne už při startu.

Při aktualizaci ze starší verze doplní instalační skript (nebo příkaz
`zabbixvms-service complete-config`) skupinu `server` s `"enabled": false` a s `host`
složeným z `location` a `_server`, například `Praha_server`; totéž dostane skupina
z verze 0.3.x s prázdným `host`. Původní soubor zůstane jako `config.json.bak`. Jméno
zkontrolujte: musí přesně odpovídat hostu serveru v Zabbixu z kroku 7.2.
S `"enabled": false` se nabití UPS nečte ani neposílá, stav agenta na host serveru chodí
dál. Změna se projeví po restartu služby.

### 7.2 Založit host serveru

V Zabbixu založte host se jménem přesně podle `host` z konfigurace, dejte ho do skupiny
hostů `VMS` a přiřaďte mu šablonu **VMS zabbix agent server**. Šablonu turbín mu
nepřiřazujte. Skupina `VMS` zajistí, že se k problémům hostu serveru rozesílají maily
podle kapitoly 5.

Host serveru má **Stav agenta** a **Poslední chybu agenta**. Nesou chyby a varování
z celého cyklu: z čtení databáze (text začíná názvem turbíny, které se týká) i z čtení
IPP. Hlídání ticha „Z hostu nepřišla žádná hodnota 5m“ mají oba typy hostů. Na hostu
serveru znamená, že agent neběží nebo se nedovolá na Zabbix, na hostu turbíny navíc, že se
z ní nedaří číst.

### 7.3 Mez nabití

Šablona nese makro `{$VMS.UPS.CHARGE.MIN}` s výchozí hodnotou **50**. Když nabití klesne
pod tuto mez, trigger *Chyba napájení* s prioritou High přejde do problémového stavu.
Nabití rovné mezi problém ještě nehlásí. Jinou mez nastavíte u hostu serveru na záložce
**Macros → Inherited and host macros** volbou **Change**, stejně jako mez otáček
v kapitole 4.

Když agent nabití z IPP nezjistí, například protože IPP neběží, odmítne přihlášení nebo
ztratil spojení s UPS, nabití v tom cyklu neposílá a hlásí chybu agenta. Co jednotlivé
texty znamenají, popisuje [přehled chyb agenta](CHYBY-agenta.md).
