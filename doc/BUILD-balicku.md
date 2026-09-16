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
zkopírovat z `dist/`, jak dělá druhý řádek. Ve složce `offline` pak bude šest souborů,
dohromady kolem 25 MB:

```
zabbixvms-0.1.0-py3-none-any.whl
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

Z příkazové řádky spuštěné jako administrátor:

```
python -m pip install --no-index --find-links C:\install\offline zabbixvms
```

`--no-index` zakáže PyPI a `--find-links` řekne, kde balíčky hledat, takže instalace proběhne
jen ze souborů. Pak se agent zaregistruje obvyklým způsobem:

```
zabbixvms-service install
```

Jestli pak služba nenastartuje, je to skoro jistě tím, že Python není nainstalovaný pro celý
stroj – viz [README](../README.md#instalace).
