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
