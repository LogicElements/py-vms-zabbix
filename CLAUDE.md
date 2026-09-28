# CLAUDE.md

Zabbix agent pro monitorování instalací VMS (viz [README.md](README.md)).

## Sdílená pravidla

@agent-general/agents.md

## Skills

Skills z `agent-general/skills/` se napojují symlinky v `.claude/skills/`. Ty se neverzují,
protože jsou lokální pro konkrétní checkout. Po naklonování repozitáře nebo po
`git submodule update` je vytvoř a zaktualizuj skriptem:

```bash
bash agent-general/scripts/sync-skills-links.sh
```

## Build

Každý build balíčku končí aktualizací složky `offline`, ze které se instaluje na servery bez
přístupu k PyPI (viz [BUILD-balicku.md](doc/BUILD-balicku.md)):

1. Spusť `build.bat`. Z Git Bashe ho `cmd //c build.bat` nenajde, spouštěj ho z PowerShellu
   celou cestou. Hlášení `NativeCommandError` v PowerShellu 5.1 je jen výstup na stderr,
   rozhoduje návratový kód.
2. `build.bat` sám smaže z `offline` předchozí `zabbixvms-*.whl` a zkopíruje tam nový wheel
   z `dist/`. Zkontroluj, že je v `offline` jediný `zabbixvms-*.whl` a má novou verzi.
3. Když se od minulého buildu změnily `dependencies` v `pyproject.toml`, stáhni do `offline`
   i závislosti podle kapitoly „Instalace na server bez přístupu k PyPI“ v BUILD-balicku.md.

Wheely v `offline` se neverzují (`.gitignore`), takže se po tomto kroku nic necommituje.
