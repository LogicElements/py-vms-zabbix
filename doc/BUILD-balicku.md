# Sestavení balíčku

Vše běží z virtuálního prostředí v `.venv`; `build.bat` se bez něj odmítne spustit.

## Příprava virtuálního prostředí

Jednou na stroji povolte aktivaci virtuálního prostředí:

```
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Vytvořte prostředí a nainstalujte balíček i nástroje pro testy a sestavení:

```
py -3.14 -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -e ".[dev]" build twine
```

Projekt vyžaduje Python 3.12 nebo novější. Pokud `py -3.14` hlásí, že verzi nezná, nebo
spustí jinou, ověřte si dostupné verze příkazem `py -0p` a použijte rovnou plnou cestu
k interpretu.

`twine` je potřeba jen pro publikování, na sestavení balíčku stačí `build`.

## Spuštění testů

```
.venv\Scripts\python -m pytest
```

Součástí sady jsou i testy proti prostředí, které jdou vynechat:

```
.venv\Scripts\python -m pytest -m "not db and not gui"
```

- `db` – testy proti testovací databázi `BVMS`; když databáze není dostupná, přeskočí se samy
- `gui` – testy, které staví skutečné okno a ikonu v systray, takže potřebují přihlášené sezení

## Číslování verzí

Verze balíčku je na jediném místě, v `src/zabbixvms/__init__.py`:

```python
__version__ = "0.2.1"
```

`pyproject.toml` si ji odtud bere (`dynamic = ["version"]`), takže se obě čísla nemají jak
rozejít.

**Verzi zvyšte u každé změny, která jde na server** – i u opravy chyby. Poslední číslo
(patch) je přesně na opravy chování, prostřední na nové schopnosti agenta. Když se číslo
nezmění, vzniknou dva různé soubory se stejným jménem: pip takový balíček považuje za už
nainstalovaný a `pip install --upgrade` starou verzi na serveru nechá. Se zvýšeným číslem
je nasazení obyčejný upgrade.

Co je na serveru nasazené, zjistíte příkazem `pip show zabbixvms`.

## Sestavení a publikování

```
build.bat
```

Skript spustí testy, smaže `dist/` i zbytky metadat v `src/*.egg-info` a sestaví sdist
a wheel interpretem z `.venv`. **Nic nepublikuje.** Selžou-li testy nebo sestavení, skončí
a nic dalšího neudělá.

Publikování je potřeba vyžádat zvlášť:

```
build.bat upload
```

Tím se po sestavení nahraje obsah `dist/` přes `twine`. Cíl určuje nastavení `twine`,
tedy `%USERPROFILE%\.pypirc` nebo přepínač `--repository`; bez uloženého tokenu se
`twine` zeptá na přihlašovací údaje.

Totéž ručně, bez skriptu:

```
.venv\Scripts\python -m build
.venv\Scripts\python -m twine upload dist/*
```

## Instalace sestaveného balíčku

Na cílovém serveru se instaluje obyčejným `pip install .` nebo z wheelu ze složky `dist/`.
Pozor na požadavek z [README](../README.md#instalace): Python musí být nainstalovaný pro
celý stroj, jinak služba nenastartuje.

## Instalace na server bez přístupu k PyPI

Servery VMS bývají odříznuté od internetu, takže se balíček i jeho závislosti musí přenést
jako soubory. Postup má tři kroky: stáhnout, přenést, nainstalovat bez sítě.

### 1. Stáhnout balíčky na stroji s internetem

Nejprve sestavte balíček (`build.bat`) a pak vedle něj stáhněte závislosti:

```
.venv\Scripts\python -m pip download . -d offline
copy dist\zabbixvms-*.whl offline\
```

`pip download .` stáhne **jen závislosti**, vlastní balíček ne – ten je potřeba do složky
zkopírovat z `dist/`, jak dělá druhý řádek. Ve složce `offline` pak bude vedle
instalačního skriptu šest wheelů, dohromady kolem 25 MB:

```
install.ps1
zabbixvms-<verze>-py3-none-any.whl
jsonpickle-4.1.2-py3-none-any.whl
mysql_connector_python-26.7.0-cp314-cp314-win_amd64.whl
pywin32-312-cp314-cp314-win_amd64.whl
pyyaml-6.0.3-cp314-cp314-win_amd64.whl
zabbix_utils-2.0.4-py3-none-any.whl
```

**Pozor na verzi Pythonu.** Wheely označené `cp314` patří Pythonu 3.14 a na serveru s jinou
verzí se nenainstalují. Když se verze liší, stahujte rovnou pro cílovou verzi a platformu;
závislosti se v tomhle režimu musí vyjmenovat, protože pip nesmí nic sestavovat:

```
.venv\Scripts\python -m pip download --only-binary=:all: --platform win_amd64 ^
    --python-version 3.12 -d offline ^
    mysql-connector-python jsonpickle zabbix_utils pywin32 PyYAML
copy dist\zabbixvms-*.whl offline\
```

Seznam závislostí odpovídá `dependencies` v `pyproject.toml`; při jeho změně upravte i tento
příkaz. Balíček samotný je `py3-none-any`, tedy na verzi Pythonu nezávislý.

### 2. Přenést složku na server

Celou složku `offline` zkopírujte na server, třeba na `C:\install\offline`.

### 3. Nainstalovat bez sítě

Ve složce leží skript `install.ps1`, který instalaci i aktualizaci provede sám. První
nasazení spusťte **jako správce**, protože registrace služby to vyžaduje:

```
powershell -ExecutionPolicy Bypass -File C:\install\offline\install.ps1
```

Žádné parametry nepotřebuje – balíčky bere ze složky, ve které sám leží. Podle toho, co na
serveru zastihne:

- **agent tam ještě není** – nainstaluje balíček i se závislostmi, zaregistruje službu
  a spustí ji,
- **je tam starší verze** – ukončí tray aplikaci, zastaví službu, vymění jen balíček
  `zabbixvms`, doplní do konfigurace položky nové verze (viz *Aktualizace už nasazeného
  agenta* níže) a službu i tray zase spustí,
- **je tam stejná nebo novější verze** – nechá ji být a jen dohlédne, že služba běží.

Než cokoli změní, ověří, že je v `PATH` Python a že wheely ve složce patří k jeho verzi.
Když něco z toho neplatí, skončí s vysvětlením a nic neudělá.

**Práva správce si vyžádá jen na to, co je opravdu potřebuje**, ne paušálně na celý běh.
Zastavit a spustit službu smějí běžní uživatelé — registrace jim to právo dala — takže běh,
který jen dohlédne na běžící službu, projde bez elevace. Elevaci si skript vyžádá ve dvou
případech: když služba ještě není zaregistrovaná, a když do složek, kam pip balíček
zapisuje, zapsat nejde. To druhé nastane u Pythonu nainstalovaného pro celý stroj, protože
jeho `site-packages` leží v `Program Files`, kam běžný uživatel psát nesmí — tam si tedy
aktualizace elevaci vyžádá dál. Skript to nehádá z toho, jestli běží jako správce, ale
zkusí do cílové složky zapsat.

Tray aplikaci skript spouští znovu ve svém vlastním sezení. Když běžela pod jiným přihlášeným
uživatelem, tomu se sama vrátí až při jeho příštím přihlášení.

Kdyby bylo potřeba totéž udělat ručně, odpovídá skript těmhle příkazům:

```
python -m pip install --no-index --find-links C:\install\offline zabbixvms
zabbixvms-service install
```

`--no-index` zakáže PyPI a `--find-links` řekne, kde balíčky hledat, takže instalace proběhne
jen ze souborů.

Jestli služba nenastartuje, je to skoro jistě tím, že Python není nainstalovaný pro celý
stroj – viz [README](../README.md#instalace). Po první instalaci ještě upravte konfiguraci
v `C:\ProgramData\LogicElements\ZabbixVms\config.json` podle dané turbíny a službu
restartujte.

## Aktualizace už nasazeného agenta

Na serveru tohle všechno udělá `install.ps1` ze složky `offline` (krok 3 výše). Zbytek téhle
kapitoly popisuje, co přesně dělá a proč.

Novou verzi **není potřeba nasazovat přes odebrání a znovunainstalování služby**. U služby
je v registru uložená jen cesta k `pythonservice.exe` a název třídy, která ji obsluhuje
(`zabbixvms.service.ZabbixVmsService`); kde balíček leží, si Python dohledá až při startu
procesu. Stačí tedy vyměnit balíček a službu restartovat:

```
zabbixvms-service stop
python -m pip install --no-index --find-links C:\install\offline ^
    --upgrade --no-deps zabbixvms
zabbixvms-service start
```

Tři věci, na kterých ten postup stojí:

- **Nejdřív zastavit službu.** Běžící proces si starý kód drží v paměti až do restartu
  a při plné reinstalaci závislostí by pip navíc nemohl přepsat knihovny pywin32, které má
  proces načtené.
- **Ukončit i tray aplikaci.** Drží otevřené `zabbixvms-tray.exe` a soubor, který má
  v ruce běžící proces, pip nevymění – skončil by chybou `WinError 32`. Zavřete ji položkou
  *Ukončit* v jejím menu nebo příkazem `Stop-Process -Name zabbixvms-tray -Force`
  a po aktualizaci ji zase spusťte; sama naběhne i při příštím přihlášení.
- **`--no-deps`** omezí výměnu jen na `zabbixvms`, takže se nesáhne na pywin32 ani na
  `pythonservice.exe`. Bez něj se reinstalují i všechny závislosti.
- **Nová verze musí mít vyšší číslo**, jinak `--upgrade` neudělá nic a pip jen oznámí
  `Requirement already satisfied` – viz *Číslování verzí* výše. Když z nějakého důvodu
  zvýšit nejde, použijte místo `--upgrade` parametr `--force-reinstall`.

Že agent zase běží, poznáte podle řádku `service ZabbixVms started` v logu
`C:\ProgramData\LogicElements\ZabbixVms\zabbixvms.log`.

Konfiguraci ve stejné složce samotná výměna balíčku nezmění. Položky, které přinesla nová
verze a v konfiguraci chybějí, si agent při načtení doplní výchozí hodnotou, se kterou pracuje
stejně jako verze, která je neznala. Týká se to jen takových položek (dnes `period`
a `raw_prefixes`); když v konfiguraci chybí cokoli jiného, třeba `system_id` turbíny, služba
nenastartuje a v logu uvede, co chybí. Výchozí hodnota by tam poslala data jiné turbíny.

Aby obsluha nové položky v souboru viděla, zapíše je tam `install.ps1` po výměně balíčku,
dokud služba stojí. Stejný krok jde udělat i ručně:

```
zabbixvms-service complete-config
```

Příkaz jen přidá chybějící položky, stávající hodnoty nechá, a původní soubor uloží vedle jako
`config.json.bak`. Když nic nechybí, soubor nezmění. Konfiguraci, kterou agent nepřijme,
nechá beze změny a skončí s chybou. Soubor zapíše po svém, takže se může změnit odsazení
a zalomení seznamů, hodnoty ne. Nespouštějte ho, když má někdo konfiguraci otevřenou
v editoru: jeho uložení by doplněné položky zase smazalo. Službu kvůli němu restartovat
netřeba, běžící agent má tytéž hodnoty doplněné v paměti.

Odebrat a znovu nainstalovat službu (`zabbixvms-service remove` a `install`) je potřeba jen
tehdy, když se mění samotné zakotvení služby:

- balíček se stěhuje do jiného prostředí Pythonu, takže vede jinudy cesta
  k `pythonservice.exe`,
- mění se název služby nebo třídy, která ji obsluhuje,
- je potřeba znovu nastavit práva ke službě, autostart tray aplikace nebo zdroj událostí.
