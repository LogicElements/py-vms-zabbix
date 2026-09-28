# Nastavení Zabbixu

Návod k nasazení šablon agenta. Nejprve se naimportuje šablona, pak se založí hosté;
kroky 1 a 3 se opakují pro každou turbínu z konfigurace. Host serveru se sledováním UPS
popisuje kapitola 7. Po aktualizaci agenta na novou verzi stačí šablonu naimportovat znovu,
nové položky a triggery se tím doplní ke stávajícím.

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

## 3. Přiřadit šablonu hostovi

V nastavení každého založeného hosta přidejte do pole **Templates** šablonu
**VMS zabbix agent** a změnu uložte. Tím na hostovi vzniknou položky pro všechny
metriky agenta i triggery hlásící jeho chyby.

Pole **Templates** je součástí formuláře hosta, takže je šablona po kroku 2 k dispozici
a jde vyplnit rovnou při zakládání hosta v kroku 1.

## 4. Mez otáček, pokud turbína nejede na 3000

Šablona nese makro `{$VMS.SPEED.NOMINAL}` s výchozí hodnotou **2500**. Pod touhle mezí se
turbína považuje za neběžící a trigger *Turbína pod nominálními otáčkami* přejde do
problémového stavu.

Ten trigger sám o sobě nic nehlásí jako poruchu – jeho smyslem je **umlčet triggery nad
stářím zápisu do bufferu** (`vms.buf_age`) **a do tabulek surových dat**
(`vms.raw_write_age`). Stojící turbína do nich nic neukládá, takže by jinak jejich stářím
poplašila dohled pokaždé, když se zastaví. Oba triggery na něm mají závislost, takže se po
dobu jeho aktivity neuplatní.

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

## 7. Host serveru a nabití UPS

Nabití baterie UPS čte agent z Eaton Intelligent Power Protector (IPP), který na serveru
UPS spravuje. Na způsobu připojení UPS k IPP nezáleží, USB i síť se čtou stejně. Nabití
se neposílá na hosty turbín, ale na samostatný host serveru, na který později přibudou
i další metriky společné celému serveru. Kapitola se dělá jednou za server.

### 7.1 Zapnout sledování v konfiguraci agenta

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
  z `location`, takže se píše celé.
- `url` je adresa webového rozhraní IPP. Výchozí `https://localhost:4680` platí, když IPP
  běží na tomtéž serveru. Adresa `http://…:4679` jen přesměrovává sem.
- `login` a `password` jsou údaje, se kterými se přihlašujete do webového rozhraní IPP.
  Heslo smí obsahovat jen znaky ASCII, tedy bez diakritiky. Jiné heslo IPP od agenta
  nepřijme a agent je proto odmítne už při startu.

Agent po aktualizaci skupinu doplní s `"enabled": false` a prázdným `host`, takže
dokud ji nevyplníte, na host serveru nic neposílá. Změna se projeví po restartu služby.

### 7.2 Založit host serveru

V Zabbixu založte host se jménem přesně podle `host` z konfigurace, dejte ho do skupiny
hostů `VMS` a přiřaďte mu šablonu **VMS zabbix agent server**. Šablonu turbín mu
nepřiřazujte. Skupina `VMS` zajistí, že se k problémům hostu serveru rozesílají maily
podle kapitoly 5.

Host serveru má vlastní **Stav agenta** a **Poslední chybu agenta**, které popisují jen
čtení z IPP. Chyba IPP se proto neobjeví na hostech turbín a výpadek databáze zase ne na
hostu serveru. Hlídání ticha „Z hostu nepřišla žádná hodnota 5m“ má host serveru také.

### 7.3 Mez nabití

Šablona nese makro `{$VMS.UPS.CHARGE.MIN}` s výchozí hodnotou **50**. Když nabití klesne
pod tuto mez, trigger *Chyba napájení* s prioritou High přejde do problémového stavu.
Nabití rovné mezi problém ještě nehlásí. Jinou mez nastavíte u hostu serveru na záložce
**Macros → Inherited and host macros** volbou **Change**, stejně jako mez otáček
v kapitole 4.

Když agent nabití z IPP nezjistí, například protože IPP neběží, odmítne přihlášení nebo
ztratil spojení s UPS, nabití v tom cyklu neposílá a hlásí chybu agenta. Co jednotlivé
texty znamenají, popisuje [přehled chyb agenta](CHYBY-agenta.md).
