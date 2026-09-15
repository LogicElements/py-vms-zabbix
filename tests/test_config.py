"""Tests of the configuration: round trip, its place in ProgramData and the
accepted ranges (UC2-R1, UC2-R3, UC2-R4, UC2-R5, UC2-R6, UC2-R7)."""

from pathlib import Path

import pytest

from zabbixvms import config as config_module
from zabbixvms.config import (
    DEFAULT_PERIOD,
    MAX_PERIOD,
    MIN_PERIOD,
    Config,
    ConfigError,
    DatabaseConfig,
    Turbine,
    ZabbixConfig,
    config_path,
    deploy_default,
    load_config,
)


def make_config():
    """Configuration with values different from the defaults of every class."""
    return Config(
        zabbix=ZabbixConfig(server="zabbix.example.com", port=10052, location="Praha"),
        database=DatabaseConfig(
            host="db.example.com",
            database="BVMS2",
            user="reader",
            password="secret",
            info_table="info_xx",
        ),
        turbines=[
            Turbine(name="TG1", system_id=11, buffers=["buffer_a"]),
            Turbine(name="TG2", system_id=12, buffers=["buffer_b", "buffer_c"]),
        ],
    )


def test_store_and_load_keeps_all_values(tmp_path):
    """UC2-R1: storing and loading again returns the same values."""
    path = tmp_path / "config.json"
    make_config().store(path)

    loaded = Config.load(path)

    original = make_config()
    assert isinstance(loaded, Config)
    assert loaded.zabbix.server == original.zabbix.server
    assert loaded.zabbix.port == original.zabbix.port
    assert loaded.zabbix.location == original.zabbix.location
    assert loaded.database.host == original.database.host
    assert loaded.database.database == original.database.database
    assert loaded.database.user == original.database.user
    assert loaded.database.password == original.database.password
    assert loaded.database.info_table == original.database.info_table
    assert [t.name for t in loaded.turbines] == [t.name for t in original.turbines]
    assert [t.system_id for t in loaded.turbines] == [t.system_id for t in original.turbines]
    assert [t.buffers for t in loaded.turbines] == [t.buffers for t in original.turbines]


def test_stored_file_carries_jsonpickle_tags(tmp_path):
    """UC2-R1: the stored file is JSON carrying the jsonpickle type tags."""
    import json

    path = tmp_path / "config.json"
    make_config().store(path)

    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["py/object"] == "zabbixvms.config.Config"
    assert data["zabbix"]["py/object"] == "zabbixvms.config.ZabbixConfig"
    assert data["database"]["py/object"] == "zabbixvms.config.DatabaseConfig"
    assert data["turbines"][0]["py/object"] == "zabbixvms.config.Turbine"


def test_turbines_do_not_share_buffers():
    """UC2-R3: values of one turbine do not reach the other turbines."""
    first = Turbine(name="TG1", system_id=11)
    second = Turbine(name="TG2", system_id=12)

    first.buffers.append("buffer_a")

    assert second.buffers == []


def test_config_path_points_into_program_data(monkeypatch, tmp_path):
    """UC2-R7: the active configuration lives in ProgramData."""
    monkeypatch.setenv("ProgramData", str(tmp_path))

    assert config_path() == tmp_path / "LogicElements" / "ZabbixVms" / "config.json"


def test_config_path_falls_back_to_default_program_data(monkeypatch):
    """UC2-R7: without the environment variable the documented path is used."""
    monkeypatch.delenv("ProgramData", raising=False)

    assert config_path() == Path(r"C:\ProgramData\LogicElements\ZabbixVms\config.json")


def test_deploy_default_creates_missing_configuration(tmp_path):
    """UC2-R7: a missing configuration is created from the packaged default."""
    path = tmp_path / "LogicElements" / "ZabbixVms" / "config.json"

    deployed = deploy_default(path)

    assert deployed == path
    assert path.read_bytes() == config_module.default_config_bytes()


def test_deploy_default_keeps_existing_configuration(tmp_path):
    """UC2-R4, UC2-R7: an existing configuration is left byte for byte alone."""
    path = tmp_path / "config.json"
    make_config().store(path)
    before = path.read_bytes()

    deploy_default(path)

    assert path.read_bytes() == before


def test_load_config_does_not_rewrite_the_file(tmp_path):
    """UC2-R4: loading the configuration does not change the file."""
    path = tmp_path / "config.json"
    make_config().store(path)
    before = path.read_bytes()

    loaded = load_config(path)

    assert loaded.zabbix.location == "Praha"
    assert path.read_bytes() == before


def test_packaged_default_is_a_valid_configuration(tmp_path):
    """UC2-R7: the default shipped in the package loads and passes validation."""
    config = load_config(tmp_path / "config.json")

    assert isinstance(config, Config)
    assert config.turbines


@pytest.mark.parametrize("count", [1, 2, 3, 4])
def test_one_to_four_turbines_are_accepted(count):
    """UC2-R3: one to four turbines are a valid configuration."""
    config = Config(turbines=[Turbine(name=f"TG{i}", system_id=i) for i in range(count)])

    config.validate()


@pytest.mark.parametrize("count", [0, 5])
def test_turbine_count_outside_the_range_is_rejected(count):
    """UC2-R3: an empty list and more than four turbines are refused."""
    config = Config(turbines=[Turbine(name=f"TG{i}", system_id=i) for i in range(count)])

    with pytest.raises(ConfigError):
        config.validate()


@pytest.mark.parametrize("count", [0, 1, 2])
def test_up_to_two_buffers_are_accepted(count):
    """UC2-R5: no buffer, one buffer and two buffers are all valid."""
    config = Config(turbines=[Turbine(buffers=[f"buffer_{i}" for i in range(count)])])

    config.validate()


def test_more_than_two_buffers_is_rejected():
    """UC2-R5: a turbine with three buffers is refused."""
    config = Config(turbines=[Turbine(buffers=["buffer_a", "buffer_b", "buffer_c"])])

    with pytest.raises(ConfigError):
        config.validate()


def test_load_config_rejects_values_outside_the_ranges(tmp_path):
    """UC2-R3: the agent refuses to work with a configuration outside the ranges."""
    path = tmp_path / "config.json"
    Config(turbines=[]).store(path)

    with pytest.raises(ConfigError):
        load_config(path)


def test_load_rejects_a_file_that_is_not_a_configuration(tmp_path):
    """UC2-R1: a file that does not decode into Config is refused."""
    path = tmp_path / "config.json"
    path.write_text('{"py/object": "builtins.object"}', encoding="utf-8")

    with pytest.raises(ConfigError):
        Config.load(path)


def test_default_period_is_five_seconds():
    """UC4-R6: an agent that is not told otherwise waits five seconds."""
    assert Config().zabbix.period == DEFAULT_PERIOD == 5


def test_period_survives_a_round_trip(tmp_path):
    """UC2-R1: the period is stored and read back like the rest."""
    path = tmp_path / "config.json"
    Config(zabbix=ZabbixConfig(period=42)).store(path)

    assert Config.load(path).zabbix.period == 42


@pytest.mark.parametrize("period", [MIN_PERIOD, 6, 60, MAX_PERIOD])
def test_period_inside_the_range_is_accepted(period):
    """UC4-R6: five to a hundred and twenty seconds are what may be set."""
    Config(zabbix=ZabbixConfig(period=period)).validate()


@pytest.mark.parametrize("period", [0, 4, 121, 3600, -5])
def test_period_outside_the_range_is_rejected(period):
    """UC4-R6: anything else is refused, like the other ranges."""
    with pytest.raises(ConfigError, match="period"):
        Config(zabbix=ZabbixConfig(period=period)).validate()


def test_period_that_is_not_a_whole_number_is_rejected():
    with pytest.raises(ConfigError):
        Config(zabbix=ZabbixConfig(period="5")).validate()


def test_a_configuration_written_before_the_period_existed_still_loads(tmp_path):
    """UC2-R7: updating the agent must not break the file already in ProgramData.

    jsonpickle never calls __init__, so a file from an older agent simply has no
    period in it; reading it would raise AttributeError.
    """
    import json

    path = tmp_path / "config.json"
    make_config().store(path)

    stored = json.loads(path.read_text(encoding="utf-8"))
    del stored["zabbix"]["period"]
    path.write_text(json.dumps(stored, indent=2), encoding="utf-8")

    loaded = Config.load(path)

    assert loaded.zabbix.period == DEFAULT_PERIOD
    loaded.validate()
