"""Tests of the configuration: round trip, its place in ProgramData, the accepted
ranges and the fields a newer agent adds (UC2-R1, UC2-R3, UC2-R4, UC2-R5, UC2-R6,
UC2-R7, UC2-R9, UC2-R10, UC6-R1, UC7-R1, UC8-R1, UC8-R2)."""

import re
from pathlib import Path

import pytest

from zabbixvms import config as config_module
from zabbixvms.config import (
    ADDED_FIELDS,
    DEFAULT_IPP_URL,
    DEFAULT_PERIOD,
    DEFAULT_TREND_TABLE,
    DEFAULT_TREND_UTC_OFFSET,
    DEFAULT_TREND_WINDOW,
    MAX_PERIOD,
    MAX_TREND_WINDOW,
    MIN_PERIOD,
    MIN_TREND_WINDOW,
    Config,
    ConfigError,
    DatabaseConfig,
    ServerConfig,
    Turbine,
    UpsConfig,
    ZabbixConfig,
    complete_config,
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
        server=ServerConfig(
            host="Praha_server",
            ups=UpsConfig(enabled=True, url="https://ipp.example.com:4680",
                          login="monitor", password="ipp-secret"),
        ),
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
    assert data["server"]["py/object"] == "zabbixvms.config.ServerConfig"
    assert data["server"]["ups"]["py/object"] == "zabbixvms.config.UpsConfig"


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
    config = Config(turbines=[Turbine(name=f"TG{i}", system_id=i) for i in range(count)],
                    server=ServerConfig(host="Praha_server"))

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
    config = Config(turbines=[Turbine(buffers=[f"buffer_{i}" for i in range(count)])],
                    server=ServerConfig(host="Praha_server"))

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
    Config(zabbix=ZabbixConfig(period=period), server=ServerConfig(host="Praha_server")).validate()


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


def test_a_turbine_has_no_raw_data_prefix_unless_told():
    """UC6-R1: an empty list is a valid configuration."""
    config = Config(turbines=[Turbine()], server=ServerConfig(host="Praha_server"))

    assert config.turbines[0].raw_prefixes == []
    config.validate()


def test_raw_data_prefixes_survive_a_round_trip(tmp_path):
    """UC6-R1: the prefixes of VMS and TVMS are stored and read back like the rest."""
    path = tmp_path / "config.json"
    Config(turbines=[Turbine(raw_prefixes=["btt_tg11", "tg11_out"])]).store(path)

    assert Config.load(path).turbines[0].raw_prefixes == ["btt_tg11", "tg11_out"]


def test_turbines_do_not_share_raw_data_prefixes():
    """UC2-R3: values of one turbine do not reach the other turbines."""
    first = Turbine(name="TG1", system_id=11)
    second = Turbine(name="TG2", system_id=12)

    first.raw_prefixes.append("btt_tg1")

    assert second.raw_prefixes == []


@pytest.mark.parametrize("prefix", ["btt_tg11", "tg11_out", "tvms_tg31", "BTT_TG2A"])
def test_a_raw_data_prefix_of_a_table_name_is_accepted(prefix):
    """UC6-R1: letters, digits and underscores are what the table names are made of."""
    Config(turbines=[Turbine(raw_prefixes=[prefix])], server=ServerConfig(host="Praha_server")).validate()


@pytest.mark.parametrize("prefix", ["btt-tg11", "btt_%", "btt tg1", "btt_tg1'", "",
                                    "btt_tgč", 11])
def test_a_raw_data_prefix_that_is_not_a_table_name_is_rejected(prefix):
    """UC6-R1: anything else would change what the LIKE pattern of the query finds."""
    with pytest.raises(ConfigError, match="raw data prefix"):
        Config(turbines=[Turbine(raw_prefixes=["btt_tg1", prefix])]).validate()


def test_the_packaged_default_carries_the_raw_data_prefixes():
    """UC6-R1: the operator sees the field in the file that is deployed."""
    import json

    stored = json.loads(config_module.default_config_bytes())

    assert all(turbine["raw_prefixes"] == [] for turbine in stored["turbines"])


def test_a_configuration_written_before_the_raw_data_prefixes_existed_still_loads(tmp_path):
    """UC6-R1: a file of an older agent has no prefixes, its turbines get none."""
    import json

    path = tmp_path / "config.json"
    make_config().store(path)

    stored = json.loads(path.read_text(encoding="utf-8"))
    for turbine in stored["turbines"]:
        del turbine["raw_prefixes"]
    path.write_text(json.dumps(stored, indent=2), encoding="utf-8")

    loaded = Config.load(path)

    assert [turbine.raw_prefixes for turbine in loaded.turbines] == [[], []]
    loaded.validate()


def store_without(path, *fields):
    """Store make_config() and take the named fields out of the file again, the way a
    file of an older agent or a slip of the operator would leave it. A field is a path
    such as ("zabbix", "period") or ("turbines", 0, "system_id")."""
    import json

    make_config().store(path)
    stored = json.loads(path.read_text(encoding="utf-8"))
    for field in fields:
        holder = stored
        for step in field[:-1]:
            holder = holder[step]
        del holder[field[-1]]
    path.write_text(json.dumps(stored, indent=2), encoding="utf-8")


# What a file written by the first release of the agent lacks.
FIRST_RELEASE = [("zabbix", "period"), ("database", "trend_table"),
                 ("database", "trend_window"), ("database", "trend_utc_offset"),
                 ("turbines", 0, "raw_prefixes"), ("turbines", 0, "trend_signals"),
                 ("turbines", 1, "raw_prefixes"), ("turbines", 1, "trend_signals"),
                 ("server",)]

# Where fill_missing() reports it filled in what FIRST_RELEASE takes out.
FIRST_RELEASE_FILLED = ["zabbix.period", "database.trend_table", "database.trend_window",
                        "database.trend_utc_offset",
                        "turbines[0].raw_prefixes", "turbines[0].trend_signals",
                        "turbines[1].raw_prefixes", "turbines[1].trend_signals", "server"]


def test_only_fields_added_after_the_first_release_may_be_missing():
    """UC2-R9: the defaults are what a configuration without the field gets, and they
    are the values the classes themselves start with."""
    assert {kind: set(fields) for kind, fields in ADDED_FIELDS.items()} == {
        ZabbixConfig: {"period"},
        DatabaseConfig: {"trend_table", "trend_window", "trend_utc_offset"},
        Turbine: {"raw_prefixes", "trend_signals"},
        Config: {"server"}}
    assert ADDED_FIELDS[ZabbixConfig]["period"] == DEFAULT_PERIOD == ZabbixConfig().period
    assert ADDED_FIELDS[Turbine]["raw_prefixes"] == [] == Turbine().raw_prefixes
    assert ADDED_FIELDS[Turbine]["trend_signals"] == [] == Turbine().trend_signals
    assert ADDED_FIELDS[DatabaseConfig]["trend_table"] == DatabaseConfig().trend_table
    assert ADDED_FIELDS[DatabaseConfig]["trend_window"] == DatabaseConfig().trend_window
    assert (ADDED_FIELDS[DatabaseConfig]["trend_utc_offset"]
            == DatabaseConfig().trend_utc_offset)


def test_a_server_group_filled_in_watches_nothing():
    """UC2-R9, UC7-R1: a configuration of an older agent has no server group; the one
    it gets has the UPS switched off, and the host is named by fill_missing()."""
    server = ADDED_FIELDS[Config]["server"]

    assert isinstance(server, ServerConfig)
    assert server.host == ""
    assert server.ups.enabled is False
    assert vars(server.ups) == vars(ServerConfig().ups)


def test_fill_missing_says_what_it_filled_in(tmp_path):
    """UC2-R9: every field that was missing, with the place it sits."""
    path = tmp_path / "config.json"
    store_without(path, *FIRST_RELEASE)

    config = Config.read(path)

    assert config.fill_missing() == FIRST_RELEASE_FILLED
    assert config.fill_missing() == []


def test_a_file_of_the_first_release_loads_without_being_written(tmp_path):
    """UC2-R4, UC2-R9: the fields are filled in memory, the file stays as it was."""
    path = tmp_path / "config.json"
    store_without(path, *FIRST_RELEASE)
    before = path.read_bytes()

    loaded = load_config(path)

    assert loaded.zabbix.period == DEFAULT_PERIOD
    assert path.read_bytes() == before


@pytest.mark.parametrize("field, named", [
    (("turbines", 0, "system_id"), "turbines[0].system_id"),
    (("turbines", 1, "name"), "turbines[1].name"),
    (("zabbix", "location"), "zabbix.location"),
    (("database", "password"), "database.password"),
    (("turbines",), "turbines"),
    (("zabbix",), "zabbix"),
    (("server", "host"), "server.host"),
    (("server", "ups"), "server.ups"),
    (("server", "ups", "password"), "server.ups.password"),
])
def test_a_missing_field_nothing_may_stand_in_for_is_refused(tmp_path, field, named):
    """UC2-R9: a default for these would send the values of another turbine or under
    another host, so the configuration is refused and says what it lacks."""
    path = tmp_path / "config.json"
    store_without(path, field)

    with pytest.raises(ConfigError, match=re.escape(f"lacks {named}")):
        Config.load(path)


def test_a_group_of_another_kind_counts_as_missing(tmp_path):
    """UC2-R9: a group without its type tag cannot be read either."""
    path = tmp_path / "config.json"
    store_without(path, ("zabbix", "py/object"))

    with pytest.raises(ConfigError, match="lacks zabbix"):
        Config.load(path)


def test_a_file_that_is_not_json_is_a_configuration_error(tmp_path):
    """A broken file is refused with a text that says so, not with a traceback."""
    path = tmp_path / "config.json"
    path.write_text('{"py/object": "zabbixvms.config.Config",', encoding="utf-8")

    with pytest.raises(ConfigError, match="cannot read configuration"):
        Config.load(path)


def test_complete_config_writes_in_the_fields_of_a_newer_agent(tmp_path):
    """UC2-R10: the missing fields reach the file with their defaults."""
    import json

    path = tmp_path / "config.json"
    store_without(path, *FIRST_RELEASE)

    added = complete_config(path)

    assert added == FIRST_RELEASE_FILLED
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored["zabbix"]["period"] == DEFAULT_PERIOD
    # Each turbine has a list of its own, not a reference to the list of the first.
    assert [turbine["raw_prefixes"] for turbine in stored["turbines"]] == [[], []]
    assert [turbine["trend_signals"] for turbine in stored["turbines"]] == [[], []]
    assert stored["database"]["trend_table"] == DEFAULT_TREND_TABLE
    assert stored["database"]["trend_window"] == DEFAULT_TREND_WINDOW
    assert Config.read(path).fill_missing() == []


def test_the_host_of_the_server_is_named_after_the_location(tmp_path):
    """UC2-R9, UC7-R1: an older file has no host of the server, so it gets the
    location and _server, which is what the installations call it."""
    path = tmp_path / "config.json"
    store_without(path, ("server",))

    config = Config.read(path)

    assert config.fill_missing() == ["server"]
    assert config.server.host == "Praha_server"
    config.validate()


def test_an_empty_host_of_the_server_is_named_too(tmp_path):
    """UC2-R9: 0.3.x wrote the group with an empty host; it is filled like a missing one."""
    import json

    path = tmp_path / "config.json"
    make_config().store(path)
    stored = json.loads(path.read_text(encoding="utf-8"))
    stored["server"]["host"] = ""
    path.write_text(json.dumps(stored, indent=2), encoding="utf-8")

    config = Config.read(path)

    assert config.fill_missing() == ["server.host"]
    assert config.server.host == "Praha_server"
    # Nothing else of the group is touched.
    assert config.server.ups.enabled is True and config.server.ups.password == "ipp-secret"


def test_a_host_of_the_server_that_is_set_is_left_alone(tmp_path):
    """UC2-R9: only a host nobody named is filled in."""
    path = tmp_path / "config.json"
    make_config().store(path)
    config = Config.read(path)
    config.server.host = "Plzen_ups"

    assert config.fill_missing() == []
    assert config.server.host == "Plzen_ups"


def test_complete_config_writes_in_the_host_of_the_server(tmp_path):
    """UC2-R10, UC7-R1: the update leaves a file the agent starts with."""
    import json

    path = tmp_path / "config.json"
    store_without(path, ("server",))

    assert complete_config(path) == ["server"]

    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored["server"]["host"] == "Praha_server"
    assert stored["server"]["ups"]["enabled"] is False
    assert load_config(path).server.host == "Praha_server"
    assert (tmp_path / "config.json.bak").exists()


def test_complete_config_writes_in_the_host_of_an_existing_empty_group(tmp_path):
    """UC2-R10: the file of 0.3.x, whose group has an empty host, is completed too."""
    import json

    path = tmp_path / "config.json"
    make_config().store(path)
    stored = json.loads(path.read_text(encoding="utf-8"))
    stored["server"]["host"] = ""
    path.write_text(json.dumps(stored, indent=2), encoding="utf-8")

    assert complete_config(path) == ["server.host"]

    assert json.loads(path.read_text(encoding="utf-8"))["server"]["host"] == "Praha_server"


def test_complete_config_keeps_every_value_that_was_there(tmp_path):
    """UC2-R10: only fields are added, nothing that was set changes."""
    path = tmp_path / "config.json"
    store_without(path, *FIRST_RELEASE)

    complete_config(path)

    loaded, original = Config.read(path), make_config()
    assert vars(loaded.database) == vars(original.database)
    assert {name: value for name, value in vars(loaded.zabbix).items()
            if name != "period"} == \
        {name: value for name, value in vars(original.zabbix).items() if name != "period"}
    assert [(t.name, t.system_id, t.buffers) for t in loaded.turbines] == \
        [(t.name, t.system_id, t.buffers) for t in original.turbines]


def test_complete_config_keeps_the_file_as_it_was_beside_it(tmp_path):
    """UC2-R10: the previous file stays as config.json.bak, and nothing else is left."""
    path = tmp_path / "config.json"
    store_without(path, *FIRST_RELEASE)
    before = path.read_bytes()

    complete_config(path)

    assert (tmp_path / "config.json.bak").read_bytes() == before
    assert sorted(entry.name for entry in tmp_path.iterdir()) == \
        ["config.json", "config.json.bak"]


def test_complete_config_leaves_a_complete_file_alone(tmp_path):
    """UC2-R10: nothing missing, nothing written and no backup."""
    path = tmp_path / "config.json"
    make_config().store(path)
    before = path.read_bytes()

    assert complete_config(path) == []
    assert path.read_bytes() == before
    assert not (tmp_path / "config.json.bak").exists()


def test_complete_config_without_a_configuration_does_nothing(tmp_path):
    """UC2-R10: a first installation has no file yet; the service deploys it."""
    path = tmp_path / "config.json"

    assert complete_config(path) == []
    assert not path.exists()


@pytest.mark.parametrize("broken", ["missing system_id", "five turbines"])
def test_complete_config_leaves_an_invalid_file_alone(tmp_path, broken):
    """UC2-R10: a configuration the agent refuses is not touched, it is reported."""
    import json

    path = tmp_path / "config.json"
    if broken == "missing system_id":
        store_without(path, *FIRST_RELEASE, ("turbines", 0, "system_id"))
    else:
        Config(turbines=[Turbine(name=f"TG{i}", system_id=i) for i in range(5)]).store(path)
        stored = json.loads(path.read_text(encoding="utf-8"))
        del stored["zabbix"]["period"]
        path.write_text(json.dumps(stored, indent=2), encoding="utf-8")
    before = path.read_bytes()

    with pytest.raises(ConfigError):
        complete_config(path)

    assert path.read_bytes() == before
    assert not (tmp_path / "config.json.bak").exists()


def test_complete_config_works_on_the_active_configuration_by_default():
    """UC2-R10: the update writes into the file in ProgramData."""
    path = config_path()
    path.parent.mkdir(parents=True)
    store_without(path, ("zabbix", "period"))

    assert complete_config() == ["zabbix.period"]


def test_the_server_group_survives_a_round_trip(tmp_path):
    """UC7-R1: the host of the server and the access to IPP are stored and read back."""
    path = tmp_path / "config.json"
    make_config().store(path)

    loaded = Config.load(path)

    assert loaded.server.host == "Praha_server"
    assert vars(loaded.server.ups) == {"enabled": True, "url": "https://ipp.example.com:4680",
                                       "login": "monitor", "password": "ipp-secret"}


def test_the_host_of_the_server_is_not_made_of_the_location():
    """UC7-R1: the host of the server is set whole, independently of location."""
    config = make_config()
    config.zabbix.location = "Brno"

    assert config.server.host == "Praha_server"


def test_ipp_is_read_on_this_server_unless_told_otherwise():
    """UC7-R1: IPP answers on the server itself, on the port its browser page uses."""
    assert UpsConfig().url == DEFAULT_IPP_URL == "https://localhost:4680"


def test_a_host_of_the_server_is_needed_with_the_ups_watched():
    """UC7-R1: without a host the charge and the state of the agent have nowhere to go."""
    config = make_config()
    config.server.host = ""

    with pytest.raises(ConfigError, match="server.host"):
        config.validate()


@pytest.mark.parametrize("host", ["", "   ", None])
def test_a_host_of_the_server_is_needed_even_without_the_ups(host):
    """UC7-R1: the host carries the state of the agent, so the UPS being off changes
    nothing about it."""
    config = make_config()
    config.server = ServerConfig(host=host)

    with pytest.raises(ConfigError, match="server.host"):
        config.validate()


def test_a_ups_that_is_not_watched_is_valid_with_a_host():
    """UC7-R1: the UPS switched off is a valid configuration as long as the host is set."""
    config = make_config()
    config.server = ServerConfig(host="Praha_server")

    config.validate()


def test_a_ipp_password_outside_ascii_is_rejected():
    """IPP hashes the password in its own JavaScript, which agrees with SHA1 only while
    the password is ASCII; the agent could never log in with anything else."""
    config = make_config()
    config.server.ups.password = "heslo-žluťoučké"

    with pytest.raises(ConfigError, match="password"):
        config.validate()


def test_the_packaged_default_carries_a_server_group_that_watches_nothing():
    """UC7-R1: the operator sees the group in the file that is deployed, with a host and
    the UPS switched off."""
    import json

    stored = json.loads(config_module.default_config_bytes())

    assert stored["server"]["host"].strip()
    assert stored["server"]["ups"]["enabled"] is False
    assert stored["server"]["ups"]["url"] == DEFAULT_IPP_URL


def test_a_switch_of_the_ups_that_is_not_true_or_false_is_rejected():
    """UC7-R1: "false" in quotes would switch the UPS on."""
    config = make_config()
    config.server.ups.enabled = "false"

    with pytest.raises(ConfigError, match="enabled"):
        config.validate()


def test_the_trend_table_is_dukovany_local_unless_set():
    """UC8-R1: a configuration that does not name the table reads the usual one."""
    assert DEFAULT_TREND_TABLE == "dukovany_local"
    assert Config().database.trend_table == "dukovany_local"
    assert Config().database.trend_window == DEFAULT_TREND_WINDOW == 10000


def test_the_trend_settings_survive_a_round_trip(tmp_path):
    """UC8-R1, UC8-R2: the table, the window and the signals are stored and read back."""
    path = tmp_path / "config.json"
    Config(database=DatabaseConfig(trend_table="trend_xx", trend_window=5000),
           turbines=[Turbine(name="TG1", trend_signals=[-4058, 7]),
                     Turbine(name="TG2")]).store(path)

    loaded = Config.load(path)

    assert loaded.database.trend_table == "trend_xx"
    assert loaded.database.trend_window == 5000
    assert loaded.turbines[0].trend_signals == [-4058, 7]
    assert loaded.turbines[1].trend_signals == []


def test_a_turbine_watches_no_trend_signal_unless_set():
    """UC8-R2: an empty list is valid, and every turbine has a list of its own."""
    first, second = Turbine(), Turbine()
    first.trend_signals.append(1)

    assert second.trend_signals == []
    Config(turbines=[Turbine(), Turbine(trend_signals=[])],
           server=ServerConfig(host="Praha_server")).validate()


def test_trend_signals_may_be_negative_whole_numbers():
    """UC8-R2: the signals of the VMS carry negative SigID."""
    Config(turbines=[Turbine(trend_signals=[-4058, -4060, -4071, -4072, -4075, -4083])],
           server=ServerConfig(host="Praha_server")).validate()


@pytest.mark.parametrize("signal", ["-4058", 1.5, None, True, [1, 2]])
def test_a_trend_signal_that_is_no_whole_number_is_rejected(signal):
    """UC8-R2: anything but a whole number is refused, a pair included."""
    with pytest.raises(ConfigError, match="trend signal"):
        Config(turbines=[Turbine(name="TG1", trend_signals=[-4058, signal])],
               server=ServerConfig(host="Praha_server")).validate()


@pytest.mark.parametrize("window", [MIN_TREND_WINDOW, 10000, MAX_TREND_WINDOW])
def test_a_trend_window_inside_the_range_is_accepted(window):
    """UC8-R1: a thousand to a million rows are what may be set."""
    Config(database=DatabaseConfig(trend_window=window),
           server=ServerConfig(host="Praha_server")).validate()


@pytest.mark.parametrize("window", [0, 999, 1000001, -1, "10000", 5000.0, True])
def test_a_trend_window_outside_the_range_is_rejected(window):
    """UC8-R1: anything else is refused, like the other ranges."""
    with pytest.raises(ConfigError, match="trend_window"):
        Config(database=DatabaseConfig(trend_window=window),
               server=ServerConfig(host="Praha_server")).validate()


@pytest.mark.parametrize("table", ["", "  ", None])
def test_an_empty_trend_table_is_rejected(table):
    """UC8-R1: the table has to have a name."""
    with pytest.raises(ConfigError, match="trend_table"):
        Config(database=DatabaseConfig(trend_table=table),
               server=ServerConfig(host="Praha_server")).validate()


def test_a_configuration_without_the_trend_fields_still_loads(tmp_path):
    """UC2-R9, UC8-R1, UC8-R2: a file of an older agent has none of them, and gets the
    table of dukovany_local, the usual window and no signal."""
    path = tmp_path / "config.json"
    store_without(path, ("database", "trend_table"), ("database", "trend_window"),
                  ("turbines", 0, "trend_signals"), ("turbines", 1, "trend_signals"))

    loaded = load_config(path)

    assert loaded.database.trend_table == DEFAULT_TREND_TABLE
    assert loaded.database.trend_window == DEFAULT_TREND_WINDOW
    assert [turbine.trend_signals for turbine in loaded.turbines] == [[], []]


def test_the_default_configuration_has_the_trend_fields():
    """UC8-R1, UC8-R2: the file the package ships names them, so the operator sees them."""
    import json

    stored = json.loads(config_module.default_config_bytes())

    assert stored["database"]["trend_table"] == "dukovany_local"
    assert stored["database"]["trend_window"] == 10000
    assert stored["turbines"][0]["trend_signals"] == []


def test_the_trend_stamps_are_utc_plus_one_unless_set():
    """UC8-R1: the software that writes them stamps in UTC+1 all year."""
    assert DEFAULT_TREND_UTC_OFFSET == 1
    assert Config().database.trend_utc_offset == 1


@pytest.mark.parametrize("offset", [None, -12, 0, 1, 2, 14])
def test_a_trend_offset_inside_the_range_is_accepted(offset, tmp_path):
    """UC8-R1: a whole number of hours or none at all, and it survives storing."""
    path = tmp_path / "config.json"
    config = Config(database=DatabaseConfig(trend_utc_offset=offset),
                    server=ServerConfig(host="Praha_server"))
    config.validate()
    config.store(path)

    assert Config.load(path).database.trend_utc_offset == offset


@pytest.mark.parametrize("offset", [-13, 15, 1.5, "1", True])
def test_a_trend_offset_outside_the_range_is_rejected(offset):
    """UC8-R1: anything else is refused, like the other ranges."""
    with pytest.raises(ConfigError, match="trend_utc_offset"):
        Config(database=DatabaseConfig(trend_utc_offset=offset),
               server=ServerConfig(host="Praha_server")).validate()


def test_a_configuration_without_the_trend_offset_gets_utc_plus_one(tmp_path):
    """UC2-R9, UC8-R1: a file of 0.5.0 has no offset and is given the default."""
    path = tmp_path / "config.json"
    store_without(path, ("database", "trend_utc_offset"))

    assert load_config(path).database.trend_utc_offset == DEFAULT_TREND_UTC_OFFSET


def test_the_default_configuration_names_the_trend_offset():
    """UC8-R1: the shipped file shows the operator the offset."""
    import json

    stored = json.loads(config_module.default_config_bytes())

    assert stored["database"]["trend_utc_offset"] == 1


def test_the_package_carries_no_password():
    """UC2-R7: neither the shipped configuration nor the defaults of the classes hold a
    password, so an installation from the package publishes none."""
    import json

    stored = json.loads(config_module.default_config_bytes())

    assert stored["database"]["password"] == ""
    assert stored["server"]["ups"]["password"] == ""
    assert DatabaseConfig().password == ""
    assert UpsConfig().password == ""
