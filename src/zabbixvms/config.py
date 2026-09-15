"""Agent configuration: the configuration classes, their file in ProgramData
and the validation of the values the operator may set."""

from __future__ import annotations

import os
from importlib import resources
from pathlib import Path

import jsonpickle

# Active configuration lives in ProgramData; the package only carries a template.
PROGRAM_DATA_SUBDIR = Path("LogicElements") / "ZabbixVms"
CONFIG_FILENAME = "config.json"
DEFAULT_CONFIG_RESOURCE = "config_default.json"

# Ranges accepted by the agent.
MIN_TURBINES = 1
MAX_TURBINES = 4
MAX_BUFFERS = 2

# Seconds between the end of one measurement cycle and the start of the next.
DEFAULT_PERIOD = 5
MIN_PERIOD = 5
MAX_PERIOD = 120


class ConfigError(Exception):
    """Configuration cannot be read or holds values outside the allowed ranges."""


class ZabbixConfig:
    """Where the collected metrics are sent and under which location."""

    def __init__(self, server: str = "zabbix.logicelements.cz", port: int = 10051,
                 location: str = "", period: int = DEFAULT_PERIOD) -> None:
        self.server = server
        self.port = port
        # Prefix of the Zabbix host name, joined with the turbine name by an underscore.
        self.location = location
        # Seconds waited between measurement cycles.
        self.period = period


class DatabaseConfig:
    """Connection to the MySQL database written by the VMS server software."""

    def __init__(self, host: str = "localhost", database: str = "BVMS", user: str = "VMS",
                 password: str = "Vms2015", info_table: str = "info_le") -> None:
        self.host = host
        self.database = database
        self.user = user
        # Stored in plain text on purpose, see UC2-R6.
        self.password = password
        self.info_table = info_table


class Turbine:
    """One monitored turbine: its name, its row in the info table and its buffers."""

    def __init__(self, name: str = "TEST", system_id: int = 10,
                 buffers: list[str] | None = None) -> None:
        self.name = name
        self.system_id = system_id
        self.buffers = list(buffers) if buffers is not None else []

    def validate(self) -> None:
        """Raise ConfigError when the turbine has more buffers than the agent supports."""
        if len(self.buffers) > MAX_BUFFERS:
            raise ConfigError(
                f"turbine {self.name!r} has {len(self.buffers)} buffers, "
                f"at most {MAX_BUFFERS} are supported"
            )


class Config:
    """Whole agent configuration, serialized to JSON by jsonpickle."""

    def __init__(self, zabbix: ZabbixConfig | None = None, database: DatabaseConfig | None = None,
                 turbines: list[Turbine] | None = None) -> None:
        self.zabbix = zabbix if zabbix is not None else ZabbixConfig()
        self.database = database if database is not None else DatabaseConfig()
        self.turbines = list(turbines) if turbines is not None else [Turbine()]

    def validate(self) -> None:
        """Raise ConfigError when the configuration is outside the allowed ranges."""
        count = len(self.turbines)
        if count < MIN_TURBINES or count > MAX_TURBINES:
            raise ConfigError(
                f"configuration has {count} turbines, "
                f"{MIN_TURBINES} to {MAX_TURBINES} are supported"
            )
        period = self.zabbix.period
        if not isinstance(period, int) or period < MIN_PERIOD or period > MAX_PERIOD:
            raise ConfigError(
                f"period is {period!r} seconds, "
                f"{MIN_PERIOD} to {MAX_PERIOD} are supported"
            )
        for turbine in self.turbines:
            turbine.validate()

    def fill_missing(self) -> "Config":
        """Give values to what a configuration written by an older agent lacks.

        jsonpickle restores the attributes the file holds and never calls __init__,
        so a file from before a field existed would leave it missing altogether and
        reading it would raise AttributeError. An agent that is updated has to keep
        working with the configuration that is already in ProgramData.
        """
        if not hasattr(self.zabbix, "period"):
            self.zabbix.period = DEFAULT_PERIOD
        return self

    @staticmethod
    def load(path: os.PathLike | str) -> "Config":
        """Read a configuration from a JSON file written by store()."""
        path = Path(path)
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as err:
            raise ConfigError(f"cannot read configuration {path}: {err}") from err

        # keys=True is the jsonpickle 5 default; passing it keeps both calls in step.
        config = jsonpickle.decode(text, keys=True)
        if not isinstance(config, Config):
            raise ConfigError(f"{path} does not hold a configuration")
        return config.fill_missing()

    def store(self, path: os.PathLike | str) -> None:
        """Write the configuration as JSON with the jsonpickle type tags."""
        path = Path(path)
        jsonpickle.set_preferred_backend("json")
        path.write_text(jsonpickle.encode(self, indent=2, keys=True) + "\n", encoding="utf-8")


def config_path() -> Path:
    """Path of the active configuration file in ProgramData."""
    program_data = os.environ.get("ProgramData", r"C:\ProgramData")
    return Path(program_data) / PROGRAM_DATA_SUBDIR / CONFIG_FILENAME


def default_config_bytes() -> bytes:
    """Default configuration template shipped inside the package."""
    resource = resources.files("zabbixvms").joinpath("data", DEFAULT_CONFIG_RESOURCE)
    return resource.read_bytes()


def deploy_default(path: os.PathLike | str | None = None) -> Path:
    """Put the packaged default in place when no configuration exists yet.

    An existing file is left untouched, so neither a restart nor a package update
    changes what the operator has set.
    """
    path = Path(path) if path is not None else config_path()
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(default_config_bytes())
    return path


def load_config(path: os.PathLike | str | None = None) -> Config:
    """Load the active configuration, deploying the default first if needed."""
    path = deploy_default(path)
    config = Config.load(path)
    config.validate()
    return config
