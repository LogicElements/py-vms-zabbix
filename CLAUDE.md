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
