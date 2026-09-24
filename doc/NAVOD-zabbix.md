# Nastavení Zabbixu

Návod k nasazení šablony agenta. Nejprve se naimportuje šablona, pak se založí hosté;
kroky 1 a 3 se opakují pro každou turbínu z konfigurace.

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

Ten trigger sám o sobě nic nehlásí jako poruchu – jeho smyslem je **umlčet trigger nad
stářím zápisu do bufferu** (`vms.buf_age`). Stojící turbína do bufferu nic neukládá, takže
by jinak jeho stářím poplašila dohled pokaždé, když se zastaví. Trigger na něm má závislost,
takže se po dobu jeho aktivity neuplatní.

Jakmile zapnete odesílání e-mailů podle kapitoly 5, má to ale jeden důsledek: priorita
Average dostane tenhle trigger nad prahovou hodnotu, takže při každém zastavení turbíny
přijde mail. Je to záměr, ne chyba nastavení; když to u některé turbíny vadí, jde ji
z rozesílání vyjmout podle 5.4.

Ostatní triggery hlásí bez ohledu na otáčky: databáze VMS setupu i oba sockety se plní
i za klidu a přeplněný buffer je problém taky. Kdyby se ukázalo, že další trigger má za
klidu mlčet, přidá se mu stejná závislost.

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
