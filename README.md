# zabbixvms

Zabbix agent pro monitorování instalací VMS od Logic Elements.

Sleduje MySQL databázi (`BVMS`), do které zapisuje serverový software VMS, a odvozené metriky o stavu systému (měřené otáčky, stáří bufferů, konfigurace a časových značek, počty řádků v bufferech) odesílá na Zabbix server jako trapper položky (`vms.speed`, `vms.buf_rows`, ...).

Balíček vznikl vyčleněním z projektu [`pyvms`](https://github.com/LogicElements/py-vms); na něm už nezávisí a s databází `BVMS` pracuje sám.

## Dokumentace

- [PRS-zabbixvms.md](doc/PRS-zabbixvms.md) – Product Requirement Specification: účel projektu, use cases a requirementy.
- [PLAN-zabbixvms.md](doc/PLAN-zabbixvms.md) – plán: rozpad requirementů do etap.
- [NAVRH-zabbixvms.md](doc/NAVRH-zabbixvms.md) – návrh struktury balíčku: jména, členění modulů a odpovědnosti.
- [NAVOD-zabbix.md](doc/NAVOD-zabbix.md) – návod k nastavení Zabbixu: založení hostů, import šablony, mez otáček a odesílání e-mailů při problému.
- [CHYBY-agenta.md](doc/CHYBY-agenta.md) – co agent hlásí, kde chyby vznikají a kde k nim hledat podrobnosti.
- [BUILD-balicku.md](doc/BUILD-balicku.md) – sestavení balíčku: virtuální prostředí, testy, `build.bat` a publikování.

## Instalace

```bash
pip install -e .
```

Běží pouze na Windows (pro integraci s Windows Service se používá `pywin32`).

Python musí být na serveru nainstalovaný **pro celý stroj** (volba „for all users"), ne jen
pro přihlášeného uživatele. Služba běží pod účtem LocalSystem a hostitelský proces
`pythonservice.exe` potřebuje najít `python3XX.dll`. U instalace jen pro uživatele leží tahle
knihovna v `%LOCALAPPDATA%`, LocalSystem ji na své cestě nemá a služba pak nenastartuje –
ohlásí se jen chyba 1053, protože proces skončí dřív, než stihne odpovědět správci služeb.

## Použití

Instalace vytvoří dva vstupní body:

- `zabbixvms-service` – služba Windows `ZabbixVms`,
- `zabbixvms-tray` – ikona v systray, spouští se bez konzolového okna.

Konfigurace (přístupové údaje k MySQL a Zabbixu, seznam monitorovaných turbín) je JSON
v souboru `C:\ProgramData\LogicElements\ZabbixVms\config.json`. Pokud soubor neexistuje,
vytvoří se při prvním spuštění z výchozí šablony dodané v balíčku; existující soubor
zůstává beze změny i při aktualizaci balíčku.

## Vývoj

Testy se spouští z kořene repozitáře:

```bash
pip install -e ".[dev]"
pytest
```

## Licence

MIT © Logic Elements s.r.o. — viz [LICENSE](LICENSE).
