# zabbixvms

Zabbix agent pro monitorování instalací VMS od Logic Elements.

Sleduje MySQL databázi (`BVMS`), do které zapisuje serverový software VMS, a odvozené metriky o stavu systému (měřené otáčky, stáří bufferů, konfigurace a časových značek, počty řádků v bufferech, ukládání a export surových dat VMS a TVMS) odesílá na Zabbix server jako trapper položky (`vms.speed`, `vms.buf_rows`, ...).

Balíček vznikl vyčleněním z projektu [`pyvms`](https://github.com/LogicElements/py-vms); na něm už nezávisí a s databází `BVMS` pracuje sám.

## Dokumentace

- [PRS-zabbixvms.md](doc/PRS-zabbixvms.md) – Product Requirement Specification: účel projektu, use cases a requirementy.
- [PLAN-zabbixvms.md](doc/PLAN-zabbixvms.md) – plán: rozpad requirementů do etap.
- [NAVRH-zabbixvms.md](doc/NAVRH-zabbixvms.md) – návrh struktury balíčku: jména, členění modulů a odpovědnosti.
- [NAVOD-zabbix.md](doc/NAVOD-zabbix.md) – návod k nastavení Zabbixu: založení hostů, import šablony, mez otáček, odesílání e-mailů při problému a prefixy tabulek surových dat.
- [CHYBY-agenta.md](doc/CHYBY-agenta.md) – co agent hlásí, kde chyby vznikají a kde k nim hledat podrobnosti.
- [BUILD-balicku.md](doc/BUILD-balicku.md) – sestavení balíčku: virtuální prostředí, testy, `build.bat` a publikování.

## Instalace

Na serveru, kde má agent běžet, se balíček nainstaluje a pak se zaregistruje služba. Druhý
příkaz zapisuje do registru, takže potřebuje **příkazovou řádku spuštěnou jako správce**:

```
pip install .
zabbixvms-service install
```

Registrace nastaví automatický start služby, práva k datové složce a spouštění tray
aplikace po přihlášení uživatele. Na serveru bez přístupu k PyPI se instaluje ze složky
`offline` – celý postup je v [BUILD-balicku.md](doc/BUILD-balicku.md).

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

Jsou to programy ve složce `Scripts` toho Pythonu, do kterého se balíček nainstaloval.
Příkazová řádka je zná jen tehdy, když je ta složka v `PATH`: u Pythonu nainstalovaného pro
celý stroj to platí vždycky, u virtuálního prostředí až po jeho aktivaci. Hlášení
`The term 'zabbixvms-service' is not recognized` znamená právě tohle, ne chybějící balíček.

Konfigurace (přístupové údaje k MySQL a Zabbixu, seznam monitorovaných turbín) je JSON
v souboru `C:\ProgramData\LogicElements\ZabbixVms\config.json`. Pokud soubor neexistuje,
vytvoří se při prvním spuštění z výchozí šablony dodané v balíčku; existující soubor
zůstává beze změny i při aktualizaci balíčku.

## Vývoj

Ve vývojovém checkoutu se instaluje editovatelně do virtuálního prostředí a testy se
spouští z kořene repozitáře:

```
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest
```

Vstupní body pak leží v `.venv\Scripts`, takže bez aktivovaného prostředí je potřeba plná
cesta – třeba `.\.venv\Scripts\zabbixvms-service.exe install`. Založení prostředí
i nastavení, které aktivaci povolí, popisuje [BUILD-balicku.md](doc/BUILD-balicku.md).

## Licence

MIT © Logic Elements s.r.o. — viz [LICENSE](LICENSE).
