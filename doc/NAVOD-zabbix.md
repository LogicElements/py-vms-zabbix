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

Ten trigger sám o sobě nic nehlásí jako poruchu – jeho smyslem je **umlčet triggery nad
stářím měřených dat** (`vms.timestamp_age`, `vms.config_age`, `vms.buf_age`). Stojící turbína
nová měření nezapisuje, takže by jinak jejich stářím poplašila dohled pokaždé, když se
zastaví. Tyhle triggery na něm mají závislost, takže se po dobu jeho aktivity neuplatní.

Nepodmíněné zůstávají `vms.info_age`, protože databáze VMS setupu se plní bez ohledu na
otáčky, a `vms.buf_rows`, protože přeplněný buffer je problém i za klidu.

Turbína s jinými nominálními otáčkami nepotřebuje vlastní šablonu, stačí makro přepsat
u hosta: v nastavení hosta záložka **Macros → Inherited and host macros**, u
`{$VMS.SPEED.NOMINAL}` zvolit **Change** a zadat vlastní hodnotu. Ostatní hosté dál jedou
podle šablony.
