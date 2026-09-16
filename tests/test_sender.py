"""Tests of sending to Zabbix against faked objects: the host name, the server the
values go to and the rejected values (UC2-R2, UC2-R5)."""

import pytest

from zabbixvms.config import Turbine, ZabbixConfig
from zabbixvms.sender import SenderError, TrapperSender, host_name


class FakeResponse:
    def __init__(self, processed=0, failed=0):
        self.processed = processed
        self.failed = failed


class FakeSender:
    """Stands in for zabbix_utils.Sender."""

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.sent = []
        self.response = FakeResponse()

    def send(self, items):
        self.sent.append(items)
        return self.response


def make_sender(zabbix=None):
    zabbix = zabbix if zabbix is not None else ZabbixConfig(location="Praha")
    created = []

    def factory(**kwargs):
        fake = FakeSender(**kwargs)
        created.append(fake)
        return fake

    return TrapperSender(zabbix, sender_factory=factory), created


def test_host_name_joins_location_and_turbine():
    """UC2-R5: the host is `<location>_<název turbíny>`."""
    assert host_name("Praha", "TG1") == "Praha_TG1"


def test_host_name_of_a_turbine():
    sender, _ = make_sender(ZabbixConfig(location="Brno"))

    assert sender.host_name(Turbine(name="TG2", system_id=12)) == "Brno_TG2"


def test_host_names_of_turbines_and_locations_do_not_collide():
    """UC2-R5: every location and turbine pair gives its own host name."""
    names = {
        host_name("Praha", "TG1"),
        host_name("Praha", "TG2"),
        host_name("Brno", "TG1"),
        host_name("Brno", "TG2"),
    }

    assert len(names) == 4


def test_sender_uses_the_server_and_port_from_the_configuration():
    """UC2-R2: values go to the address and port of the configuration."""
    zabbix = ZabbixConfig(server="zabbix.example.com", port=10052, location="Praha")

    _, created = make_sender(zabbix)

    assert created[0].kwargs == {"server": "zabbix.example.com", "port": 10052}


def test_values_are_sent_under_the_host_of_the_turbine():
    sender, created = make_sender(ZabbixConfig(location="Praha"))
    turbine = Turbine(name="TG1", system_id=11)

    sender.send(turbine, {"vms.speed": 3000.5, "vms.buf_rows": 42})

    items = created[0].sent[0]
    assert [item.host for item in items] == ["Praha_TG1", "Praha_TG1"]
    assert [item.key for item in items] == ["vms.speed", "vms.buf_rows"]
    assert [item.value for item in items] == ["3000.5", "42"]


def test_every_value_is_sent():
    sender, created = make_sender()
    values = {f"vms.key_{index}": index for index in range(10)}

    sender.send(Turbine(name="TG1", system_id=11), values)

    assert len(created[0].sent[0]) == len(values)


def test_rejected_values_are_an_error():
    """UC2-R2: values the trapper refuses are reported as an error."""
    sender, created = make_sender()
    created[0].response = FakeResponse(processed=8, failed=2)

    with pytest.raises(SenderError, match="2"):
        sender.send(Turbine(name="TG1", system_id=11), {"vms.speed": 1.0})


def test_accepted_values_are_no_error():
    sender, created = make_sender()
    created[0].response = FakeResponse(processed=10, failed=0)

    sender.send(Turbine(name="TG1", system_id=11), {"vms.speed": 1.0})
