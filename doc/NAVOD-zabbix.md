# Nastavení Zabbixu

Návod k nasazení šablony agenta. Postup se opakuje pro každou turbínu z konfigurace.

## 1. Založit hosta

Pro každou turbínu založte v Zabbixu hosta se jménem ve tvaru
`<location>_<název turbíny>`, tedy hodnota `location` ze skupiny `zabbix` v konfiguraci
a název turbíny spojené podtržítkem. Při `location` `Praha` a turbíně `TG1` je jméno
hosta `Praha_TG1`.

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
