# vms-zabbix-agent

Zabbix monitoring agent for Logic Elements VMS deployments.

It watches a MySQL database (`BVMS`) that VMS server software writes into, and forwards derived health metrics (measured speed, buffer/config/timestamp ages, buffer row counts) to a Zabbix server as trapper items (`vms.speed`, `vms.buf_rows_1`, ...).

This package was split out of [`pyvms`](https://github.com/LogicElements/py-vms), which it depends on for reading back data from the `BVMS` database (`pyvms.DbMySql.DbMysql`).

## Installation

```bash
pip install -e .
```

Runs on Windows only (uses `pywin32` for the Windows Service integration).

## Usage

Run in the foreground for testing:

```bash
python -m zabagent.ZabAgent
```

Install and run as a Windows Service (`ZabAgent`):

```bash
python -m zabagent.ZabAgent install
python -m zabagent.ZabAgent start
```

Configuration (MySQL and Zabbix connection details, list of monitored generators) is stored as JSON at `src/zabagent/data/config_default.json` and loaded via `ZabConfig.Config`.

## License

MIT © Logic Elements s.r.o. — see [LICENSE](LICENSE).
