# vms-zabbix-agent

Zabbix agent pro monitorování instalací VMS od Logic Elements.

Sleduje MySQL databázi (`BVMS`), do které zapisuje serverový software VMS, a odvozené metriky o stavu systému (měřené otáčky, stáří bufferů, konfigurace a časových značek, počty řádků v bufferech) odesílá na Zabbix server jako trapper položky (`vms.speed`, `vms.buf_rows_1`, ...).

Balíček byl vyčleněn z projektu [`pyvms`](https://github.com/LogicElements/py-vms), na kterém závisí kvůli čtení dat z databáze `BVMS` (`pyvms.DbMySql.DbMysql`).

## Instalace

```bash
pip install -e .
```

Běží pouze na Windows (pro integraci s Windows Service se používá `pywin32`).

## Použití

Spuštění na popředí pro testování:

```bash
python -m zabagent.ZabAgent
```

Instalace a spuštění jako služba Windows (`ZabAgent`):

```bash
python -m zabagent.ZabAgent install
python -m zabagent.ZabAgent start
```

Konfigurace (přístupové údaje k MySQL a Zabbixu, seznam monitorovaných generátorů) je uložena jako JSON v souboru `src/zabagent/data/config_default.json` a načítá se přes `ZabConfig.Config`.

## Licence

MIT © Logic Elements s.r.o. — viz [LICENSE](LICENSE).
