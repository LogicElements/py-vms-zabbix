"""Agent configuration: the configuration classes, their file in ProgramData
and the validation of the values the operator may set."""

from __future__ import annotations

import copy
import os
import re
import shutil
from importlib import resources
from pathlib import Path

import jsonpickle

# Active configuration lives in ProgramData; the package only carries a template.
PROGRAM_DATA_SUBDIR = Path("LogicElements") / "ZabbixVms"
CONFIG_FILENAME = "config.json"
DEFAULT_CONFIG_RESOURCE = "config_default.json"

# Where complete_config() keeps the file as it was before it wrote into it.
BACKUP_SUFFIX = ".bak"

# Ranges accepted by the agent.
MIN_TURBINES = 1
MAX_TURBINES = 4
MAX_BUFFERS = 2

# A raw data prefix ends up in a LIKE pattern, where % or a quote would quietly change
# which tables the query finds; letters, digits and the underscore are all a table
# name of VMS or TVMS needs.
RAW_PREFIX = re.compile(r"[A-Za-z0-9_]+")

# Seconds between the end of one measurement cycle and the start of the next.
DEFAULT_PERIOD = 5
MIN_PERIOD = 5
MAX_PERIOD = 120

# Eaton IPP answers on the server it runs on; plain HTTP on 4679 only redirects here.
DEFAULT_IPP_URL = "https://localhost:4680"


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
    """One monitored turbine: its name, its row in the info table, its buffers and the
    prefixes of its raw data tables."""

    def __init__(self, name: str = "TEST", system_id: int = 10,
                 buffers: list[str] | None = None,
                 raw_prefixes: list[str] | None = None) -> None:
        self.name = name
        self.system_id = system_id
        self.buffers = list(buffers) if buffers is not None else []
        # Raw data tables of VMS and TVMS alike, named <prefix>_<date>, see UC6.
        self.raw_prefixes = list(raw_prefixes) if raw_prefixes is not None else []

    def validate(self) -> None:
        """Raise ConfigError when the turbine has more buffers than the agent supports
        or a raw data prefix that is not a plain table name."""
        if len(self.buffers) > MAX_BUFFERS:
            raise ConfigError(
                f"turbine {self.name!r} has {len(self.buffers)} buffers, "
                f"at most {MAX_BUFFERS} are supported"
            )
        for prefix in self.raw_prefixes:
            if not isinstance(prefix, str) or not RAW_PREFIX.fullmatch(prefix):
                raise ConfigError(
                    f"turbine {self.name!r} has raw data prefix {prefix!r}, only "
                    f"letters, digits and underscores are allowed"
                )


class UpsConfig:
    """Access to Eaton Intelligent Power Protector, which reports the UPS of the server."""

    def __init__(self, enabled: bool = False, url: str = DEFAULT_IPP_URL,
                 login: str = "admin", password: str = "") -> None:
        self.enabled = enabled
        # Address of the web interface of IPP, without the path of its services.
        self.url = url
        self.login = login
        # Stored in plain text, like the password of the database.
        self.password = password


class ServerConfig:
    """Metrics of the server as a whole, sent under a host of their own."""

    def __init__(self, host: str = "", ups: UpsConfig | None = None) -> None:
        # Whole name of the Zabbix host; unlike a turbine it is not made of location.
        self.host = host
        self.ups = ups if ups is not None else UpsConfig()

    def validate(self) -> None:
        """Raise ConfigError when the UPS is watched without a host to send it to, or
        with a password IPP's login cannot take."""
        # "false" in quotes would be true, and the UPS watched against the operator's
        # intent.
        if not isinstance(self.ups.enabled, bool):
            raise ConfigError(f"server.ups.enabled is {self.ups.enabled!r}, "
                              f"true or false is expected")
        if not self.ups.enabled:
            return
        if not isinstance(self.host, str) or not self.host.strip():
            raise ConfigError("server.host is empty, the UPS is watched only with "
                              "a Zabbix host of the server to send it to")
        # IPP hashes the password with its own SHA1 in JavaScript, which reads the
        # characters of the text instead of its bytes; only for ASCII does that agree
        # with SHA1, so any other password could never log in.
        if not isinstance(self.ups.password, str) or not self.ups.password.isascii():
            raise ConfigError("server.ups.password may hold ASCII characters only, "
                              "IPP cannot take any other")


class Config:
    """Whole agent configuration, serialized to JSON by jsonpickle."""

    def __init__(self, zabbix: ZabbixConfig | None = None, database: DatabaseConfig | None = None,
                 turbines: list[Turbine] | None = None,
                 server: ServerConfig | None = None) -> None:
        self.zabbix = zabbix if zabbix is not None else ZabbixConfig()
        self.database = database if database is not None else DatabaseConfig()
        self.turbines = list(turbines) if turbines is not None else [Turbine()]
        self.server = server if server is not None else ServerConfig()

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
        self.server.validate()

    def _parts(self):
        """Every group of the configuration: where it sits and what it has to be.

        The configuration itself comes last, under an empty place: the server group it
        may lack is only looked into once it is there.
        """
        yield "zabbix", self.zabbix, ZabbixConfig
        yield "database", self.database, DatabaseConfig
        for index, turbine in enumerate(self.turbines):
            yield f"turbines[{index}]", turbine, Turbine
        if hasattr(self, "server"):
            yield "server", self.server, ServerConfig
            if isinstance(self.server, ServerConfig) and hasattr(self.server, "ups"):
                yield "server.ups", self.server.ups, UpsConfig
        yield "", self, Config

    def missing_fields(self) -> list[str]:
        """What the configuration lacks that no default may stand in for.

        A group that is something else than it should be counts as missing, since
        none of its fields can be read either.
        """
        missing = [name for name in vars(Config())
                   if name not in ADDED_FIELDS[Config] and not hasattr(self, name)]
        if missing:
            return missing
        if not isinstance(self.turbines, list):
            return ["turbines"]
        for place, part, kind in self._parts():
            if not isinstance(part, kind):
                missing.append(place)
                continue
            optional = ADDED_FIELDS.get(kind, {})
            missing.extend(_place_of(place, name) for name in vars(kind())
                           if name not in optional and not hasattr(part, name))
        return missing

    def fill_missing(self) -> list[str]:
        """Give the fields of ADDED_FIELDS to a configuration written before them.

        jsonpickle restores the attributes the file holds and never calls __init__,
        so a file from before a field existed would leave it missing altogether and
        reading it would raise AttributeError. An agent that is updated has to keep
        working with the configuration that is already in ProgramData. Returns where
        a value was filled in, such as turbines[0].raw_prefixes.
        """
        filled = []
        for place, part, kind in self._parts():
            for name, default in ADDED_FIELDS.get(kind, {}).items():
                if not hasattr(part, name):
                    # Every turbine gets a list of its own; one shared list would be
                    # written out as a reference to where it first appeared.
                    setattr(part, name, copy.deepcopy(default))
                    filled.append(_place_of(place, name))
        return filled

    @staticmethod
    def read(path: os.PathLike | str) -> "Config":
        """The configuration exactly as the file holds it, with nothing filled in.

        A file that lacks anything but the fields of ADDED_FIELDS is refused here.
        """
        path = Path(path)
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as err:
            raise ConfigError(f"cannot read configuration {path}: {err}") from err

        try:
            # keys=True is the jsonpickle 5 default; passing it keeps both calls in step.
            config = jsonpickle.decode(text, keys=True)
        except Exception as err:
            # jsonpickle tries every backend it has loaded and raises what the last one
            # did, which may be YAML's error for a file that is broken JSON.
            raise ConfigError(f"cannot read configuration {path}: {err}") from err
        if not isinstance(config, Config):
            raise ConfigError(f"{path} does not hold a configuration")
        missing = config.missing_fields()
        if missing:
            raise ConfigError(f"{path} lacks {', '.join(missing)}")
        return config

    @staticmethod
    def load(path: os.PathLike | str) -> "Config":
        """Read a configuration from a JSON file written by store(), with the fields
        of a newer agent filled in."""
        config = Config.read(path)
        config.fill_missing()
        return config

    def store(self, path: os.PathLike | str) -> None:
        """Write the configuration as JSON with the jsonpickle type tags."""
        path = Path(path)
        jsonpickle.set_preferred_backend("json")
        path.write_text(jsonpickle.encode(self, indent=2, keys=True) + "\n", encoding="utf-8")


# Fields that came after the first release of the agent, with the value that makes an
# agent reading a file without them work the way the version before them did. These,
# and only these, may be missing: any other gap is a mistake in the file, and a default
# standing in for it - the system_id of another turbine, an empty location - would send
# wrong values instead of refusing to start.
ADDED_FIELDS = {
    ZabbixConfig: {"period": DEFAULT_PERIOD},
    Turbine: {"raw_prefixes": []},
    # Without a host and with the UPS switched off nothing is sent to a server host.
    Config: {"server": ServerConfig()},
}


def _place_of(place: str, name: str) -> str:
    """Where a field sits, such as turbines[0].raw_prefixes, or server at the top."""
    return f"{place}.{name}" if place else name


def data_folder() -> Path:
    """Folder in ProgramData that holds everything the agent writes.

    The configuration, the log and the rights the installation grants all point here,
    and so does the item of the tray menu that opens it.
    """
    program_data = os.environ.get("ProgramData", r"C:\ProgramData")
    return Path(program_data) / PROGRAM_DATA_SUBDIR


def config_path() -> Path:
    """Path of the active configuration file in ProgramData."""
    return data_folder() / CONFIG_FILENAME


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


def complete_config(path: os.PathLike | str | None = None) -> list[str]:
    """Write the fields a newer agent added into the configuration file.

    Meant for an update, while the service is stopped: the agent itself never writes
    the file (UC2-R4) and fills those fields in memory only. Writing them in shows the
    operator what can be set. The values already there stay as they are and the file
    as it was is kept beside it with BACKUP_SUFFIX; a file that lacks nothing, is not
    there yet or is not valid is left alone. Returns what was added.
    """
    path = Path(path) if path is not None else config_path()
    if not path.exists():
        return []
    config = Config.read(path)
    added = config.fill_missing()
    if not added:
        return []
    config.validate()

    shutil.copy2(path, path.with_name(path.name + BACKUP_SUFFIX))
    # Written aside and moved over, so an interrupted write never leaves a broken
    # configuration behind.
    fresh = path.with_name(path.name + ".tmp")
    config.store(fresh)
    os.replace(fresh, path)
    return added
