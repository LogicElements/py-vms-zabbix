"""Tests of the measurement loop against faked objects: every turbine of the
configuration, the delay between cycles, surviving a failed cycle and the host of the
server beside the turbines (UC1-R4, UC4-R6, UC5-R3, UC7-R2, UC7-R3, UC7-R4)."""

import logging

import pytest

from zabbixvms.log import log as agent_log
from zabbixvms import metrics
from zabbixvms.agent import (
    CHARGE_KEY,
    CYCLE_DELAY,
    TOLERATED_SEND_FAILURES,
    ERROR,
    ERROR_KEY,
    MAX_ERROR_LENGTH,
    OK,
    STATUS_KEY,
    WARNING,
    Agent,
)
from zabbixvms.config import Config, ServerConfig, Turbine, UpsConfig, ZabbixConfig
from zabbixvms.sender import SenderError, ZabbixUnreachable
from zabbixvms.ups import IppClient, IppError


class FakeCollector:
    def __init__(self, values=None, fail_on=(), warnings=()):
        self.values = values if values is not None else {"vms.speed": 1.0}
        self.fail_on = set(fail_on)
        self.warnings = list(warnings)
        self._warn = list(warnings)
        self.collected = []
        self.connects = 0
        self.closes = 0
        self.is_connected = False
        self._cycle = 0

    def connect(self):
        self.connects += 1
        self.is_connected = True

    def close(self):
        if self.is_connected:
            self.closes += 1
        self.is_connected = False

    def collect(self, turbine, now=None):
        self.collected.append(turbine.name)
        self.warnings = list(self._warn)
        if len(self.collected) in self.fail_on:
            raise RuntimeError("database is away")
        return dict(self.values)


class FakeSender:
    """Keeps the metric values and the state of the agent apart, as two sends."""

    def __init__(self, fail_on=(), fail_state=False, unreachable_on=(),
                 server_fail_on=(), server_unreachable_on=()):
        self.fail_on = set(fail_on)
        self.fail_state = fail_state
        # Cycles in which the values do not get to Zabbix at all, as opposed to fail_on,
        # where they arrive and are turned down.
        self.unreachable_on = set(unreachable_on)
        # The same for the values of the server host, counted by its own sends.
        self.server_fail_on = set(server_fail_on)
        self.server_unreachable_on = set(server_unreachable_on)
        self.sent = []
        self.states = []
        self.server_sent = []
        self.server_states = []

    def send_to(self, host, values):
        if STATUS_KEY in values:
            self.server_states.append((host, values))
            if self.fail_state:
                raise RuntimeError("Zabbix is away")
            return
        self.server_sent.append((host, values))
        if len(self.server_sent) in self.server_unreachable_on:
            raise ZabbixUnreachable(
                "Couldn't connect to all of cluster nodes: [zabbix.example.com:10051]")
        if len(self.server_sent) in self.server_fail_on:
            raise SenderError("Zabbix rejected 1 of 1 values of host Praha_server")

    def send(self, turbine, values):
        if STATUS_KEY in values:
            self.states.append((turbine.name, values))
            if self.fail_state:
                raise RuntimeError("Zabbix is away")
            return
        self.sent.append((turbine.name, values))
        if len(self.sent) in self.unreachable_on:
            raise ZabbixUnreachable(
                "Couldn't connect to all of cluster nodes: [zabbix.example.com:10051]")
        if len(self.sent) in self.fail_on:
            raise RuntimeError("Zabbix is away")


class FakeClock:
    """Sleep that records the delays and stops the loop after a few cycles."""

    def __init__(self, agent_holder, cycles=2):
        self.delays = []
        self.agent_holder = agent_holder
        self.cycles = cycles

    def __call__(self, seconds):
        self.delays.append(seconds)
        if len(self.delays) >= self.cycles:
            self.agent_holder[0].stop()


class FakeUps:
    """Stands in for IppClient: a charge per cycle, or the error of that cycle."""

    def __init__(self, charges=(87,), fail_on=()):
        self.charges = list(charges)
        self.fail_on = set(fail_on)
        self.reads = 0

    def charge(self):
        self.reads += 1
        if self.reads in self.fail_on:
            raise IppError("IPP at https://localhost:4680 cannot be reached: refused")
        return self.charges[min(self.reads, len(self.charges)) - 1]


def make_agent(turbines=None, collector=None, sender=None, cycles=2, ups=None,
               server=None):
    config = Config(
        zabbix=ZabbixConfig(location="Praha"),
        turbines=turbines if turbines is not None else [Turbine(name="TG1", system_id=11)],
        server=server,
    )
    holder = []
    clock = FakeClock(holder, cycles=cycles)
    agent = Agent(
        config,
        collector=collector if collector is not None else FakeCollector(),
        sender=sender if sender is not None else FakeSender(),
        sleep=clock,
        ups=ups,
    )
    holder.append(agent)
    return agent, clock


def watched_server(host="Praha_server"):
    """Server group with the UPS switched on."""
    return ServerConfig(host=host, ups=UpsConfig(enabled=True, password="secret"))


def test_cycle_covers_every_turbine():
    """UC4-R6: one cycle sends the metrics of all turbines of the configuration."""
    turbines = [Turbine(name="TG1", system_id=11), Turbine(name="TG2", system_id=12),
                Turbine(name="TG3", system_id=13)]
    collector = FakeCollector()
    sender = FakeSender()
    agent, _ = make_agent(turbines, collector, sender)

    agent.cycle()

    assert collector.collected == ["TG1", "TG2", "TG3"]
    assert [name for name, _ in sender.sent] == ["TG1", "TG2", "TG3"]


def test_collected_values_are_the_ones_sent():
    collector = FakeCollector(values={"vms.speed": 3000.5})
    sender = FakeSender()
    agent, _ = make_agent(collector=collector, sender=sender)

    agent.cycle()

    assert sender.sent[0][1] == {"vms.speed": 3000.5}


def test_loop_waits_five_seconds_between_cycles():
    """UC4-R6: five seconds pass between the cycles unless told otherwise."""
    agent, clock = make_agent(cycles=3)

    agent.run()

    assert clock.delays == [CYCLE_DELAY, CYCLE_DELAY, CYCLE_DELAY]
    assert CYCLE_DELAY == 5


def test_loop_waits_what_the_configuration_says():
    """UC4-R6: the period comes from the configuration, not from a constant."""
    config = Config(zabbix=ZabbixConfig(location="Praha", period=45),
                    turbines=[Turbine(name="TG1", system_id=11)])
    holder = []
    clock = FakeClock(holder, cycles=2)
    agent = Agent(config, collector=FakeCollector(), sender=FakeSender(), sleep=clock)
    holder.append(agent)

    agent.run()

    assert agent.period == 45
    assert clock.delays == [45, 45]


def test_loop_repeats_the_cycle():
    collector = FakeCollector()
    agent, _ = make_agent(collector=collector, cycles=3)

    agent.run()

    assert collector.collected == ["TG1", "TG1", "TG1"]


def test_loop_survives_a_database_error():
    """UC1-R4: an unreachable database does not end the loop."""
    collector = FakeCollector(fail_on=[1])
    sender = FakeSender()
    agent, _ = make_agent(collector=collector, sender=sender, cycles=3)

    agent.run()

    assert len(collector.collected) == 3
    assert [name for name, _ in sender.sent] == ["TG1", "TG1"]


def test_loop_survives_a_zabbix_error():
    """UC1-R4: an unreachable Zabbix does not end the loop either."""
    sender = FakeSender(fail_on=[1])
    agent, _ = make_agent(sender=sender, cycles=3)

    agent.run()

    assert len(sender.sent) == 3


def test_loop_picks_up_after_the_cause_is_gone():
    """UC1-R4: sending continues once the source is available again."""
    collector = FakeCollector(fail_on=[1])
    agent, _ = make_agent(collector=collector, cycles=3)

    agent.run()

    assert agent.last_error is None


def test_failed_cycle_is_remembered():
    collector = FakeCollector(fail_on=[1, 2, 3])
    agent, _ = make_agent(collector=collector, cycles=2)

    agent.run()

    assert isinstance(agent.last_error, RuntimeError)


def test_failed_cycle_drops_the_connection_so_the_next_reconnects():
    """A broken connection is not reused; the next cycle connects again."""
    collector = FakeCollector(fail_on=[1])
    agent, _ = make_agent(collector=collector, cycles=3)

    agent.run()

    assert collector.connects == 2


def test_connection_is_opened_once_while_it_holds():
    collector = FakeCollector()
    agent, _ = make_agent(collector=collector, cycles=3)

    agent.run()

    assert collector.connects == 1


def test_stop_ends_the_loop_and_closes_the_connection():
    collector = FakeCollector()
    agent, _ = make_agent(collector=collector, cycles=1)

    agent.run()

    assert not agent.running
    assert not collector.is_connected


def test_cycle_error_reaches_the_caller():
    """cycle() itself does not swallow anything; only run() keeps going."""
    collector = FakeCollector(fail_on=[1])
    agent, _ = make_agent(collector=collector)

    with pytest.raises(RuntimeError):
        agent.cycle()


def test_state_is_sent_to_every_turbine_every_cycle():
    """UC5-R3: both state metrics go to the host of every turbine, each cycle."""
    turbines = [Turbine(name="TG1", system_id=11), Turbine(name="TG2", system_id=12)]
    sender = FakeSender()
    agent, _ = make_agent(turbines, sender=sender, cycles=2)

    agent.run()

    assert [name for name, _ in sender.states] == ["TG1", "TG2", "TG1", "TG2"]
    for _, values in sender.states:
        assert set(values) == {STATUS_KEY, ERROR_KEY}


def test_clean_cycle_reports_zero_and_no_text():
    """UC5-R3: a cycle without a problem is state 0 with an empty text."""
    sender = FakeSender()
    agent, _ = make_agent(sender=sender, cycles=1)

    agent.run()

    assert agent.status == OK
    assert sender.states[0][1] == {STATUS_KEY: OK, ERROR_KEY: ""}


def test_warning_reports_one_and_its_text():
    """UC5-R3: a warning the agent carries on from is state 1 with its text."""
    collector = FakeCollector(warnings=["tabulka 'buffer_le' v databázi není"])
    sender = FakeSender()
    agent, _ = make_agent(collector=collector, sender=sender, cycles=1)

    agent.run()

    assert agent.status == WARNING
    assert sender.states[0][1][STATUS_KEY] == WARNING
    assert "buffer_le" in sender.states[0][1][ERROR_KEY]


def test_failed_cycle_reports_two_and_the_error():
    """UC5-R3: an error that stops values from being had or sent is state 2."""
    collector = FakeCollector(fail_on=[1])
    sender = FakeSender()
    agent, _ = make_agent(collector=collector, sender=sender, cycles=1)

    agent.run()

    assert agent.status == ERROR
    assert sender.states[0][1][STATUS_KEY] == ERROR
    assert "database is away" in sender.states[0][1][ERROR_KEY]


def test_state_returns_to_zero_once_the_cause_is_gone():
    """A cycle that works again clears the state and the text."""
    collector = FakeCollector(fail_on=[1])
    sender = FakeSender()
    agent, _ = make_agent(collector=collector, sender=sender, cycles=2)

    agent.run()

    assert [values[STATUS_KEY] for _, values in sender.states] == [ERROR, OK]
    assert sender.states[-1][1][ERROR_KEY] == ""


def test_error_text_is_cut_to_the_length_of_the_item():
    """UC5-R3: the text is cut to 255 characters, the size of a Character item."""
    collector = FakeCollector()

    def too_long(turbine, now=None):
        raise RuntimeError("x" * 400)

    collector.collect = too_long
    sender = FakeSender()
    agent, _ = make_agent(collector=collector, sender=sender, cycles=1)

    agent.run()

    assert len(sender.states[0][1][ERROR_KEY]) == MAX_ERROR_LENGTH == 255


def test_state_is_sent_even_when_the_cycle_failed():
    """The operator must see why no values arrived."""
    collector = FakeCollector(fail_on=[1, 2, 3])
    sender = FakeSender()
    agent, _ = make_agent(collector=collector, sender=sender, cycles=2)

    agent.run()

    assert sender.sent == []
    assert len(sender.states) == 2


def test_unsendable_state_does_not_end_the_loop():
    """UC1-R4: when Zabbix is the thing that is down, the loop carries on."""
    sender = FakeSender(fail_state=True)
    agent, clock = make_agent(sender=sender, cycles=3)

    agent.run()

    assert len(clock.delays) == 3


class CollectingHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(record)


@pytest.fixture
def written_records():
    """What the agent wrote to the log of the package during one test."""
    handler = CollectingHandler()
    agent_log.addHandler(handler)
    yield handler.records
    agent_log.removeHandler(handler)


def test_unreachable_source_or_target_is_written_to_the_log(written_records):
    """UC5-R1: MySQL and Zabbix being away is recorded, with the reason."""
    collector = FakeCollector(fail_on=[1, 2])
    agent, _ = make_agent(collector=collector, cycles=1)

    agent.run()

    assert any(record.levelno == logging.ERROR and "database is away" in record.getMessage()
               for record in written_records)


def test_rejected_values_are_written_to_the_log(written_records):
    """UC5-R1: values Zabbix refuses end up in the log as an error."""
    sender = FakeSender(fail_on=[1, 2])
    agent, _ = make_agent(sender=sender, cycles=1)

    agent.run()

    assert any("Zabbix is away" in record.getMessage() for record in written_records)


def test_warning_is_written_to_the_log(written_records):
    """UC5-R1, UC5-R3: the text of the warning matches what the log holds."""
    collector = FakeCollector(warnings=["tabulka chybí"])
    agent, _ = make_agent(collector=collector, cycles=1)

    agent.run()

    assert any(record.levelno == logging.WARNING and "tabulka chybí" in record.getMessage()
               for record in written_records)


def test_an_unreachable_zabbix_is_not_reported_as_an_error():
    """UC5-R3: the report could only travel once the connection is back, when it is
    stale, so nothing about the outage is published at all."""
    sender = FakeSender(unreachable_on=[1])
    agent, _ = make_agent(sender=sender, cycles=1)

    agent.run()

    assert agent.status == OK
    assert agent.error_text == ""
    assert sender.states == []


def test_a_short_outage_leaves_the_log_alone(caplog):
    """UC5-R3: fewer failures in a row than the agent tolerates say nothing anywhere."""
    sender = FakeSender(unreachable_on=range(1, TOLERATED_SEND_FAILURES))
    agent, _ = make_agent(sender=sender, cycles=TOLERATED_SEND_FAILURES - 1)

    with caplog.at_level(logging.ERROR, logger=agent_log.name):
        agent.run()

    assert agent.failed_sends == TOLERATED_SEND_FAILURES - 1
    assert caplog.records == []


def test_an_outage_that_keeps_going_reaches_the_log_once(caplog):
    """UC5-R3: the log says so on the agreed failure, and does not repeat itself."""
    sender = FakeSender(unreachable_on=range(1, TOLERATED_SEND_FAILURES + 3))
    agent, _ = make_agent(sender=sender, cycles=TOLERATED_SEND_FAILURES + 2)

    with caplog.at_level(logging.ERROR, logger=agent_log.name):
        agent.run()

    errors = [record for record in caplog.records if record.levelno == logging.ERROR]
    assert len(errors) == 1
    assert "Zabbix" in errors[0].getMessage()


def test_values_getting_through_again_start_the_count_afresh():
    """UC5-R3: outages are counted in a row, so one success wipes the tally."""
    sender = FakeSender(unreachable_on=[1, 3])
    agent, _ = make_agent(sender=sender, cycles=3)

    agent.run()

    assert agent.failed_sends == 1
    assert agent.status == OK


def test_rejected_values_are_still_an_error():
    """UC5-R3: a host Zabbix does not know is a fault somebody has to fix, and saying
    so works, because the connection to Zabbix is up."""
    sender = FakeSender(fail_on=[1])
    agent, _ = make_agent(sender=sender, cycles=1)

    agent.run()

    assert agent.status == ERROR
    assert sender.states != []



def test_the_charge_of_the_ups_goes_to_the_host_of_the_server():
    """UC7-R2: every cycle the charge is read and sent under the host of the server."""
    sender = FakeSender()
    ups = FakeUps(charges=[87, 64])
    agent, _ = make_agent(sender=sender, ups=ups, server=watched_server(), cycles=2)

    agent.run()

    assert sender.server_sent == [("Praha_server", {CHARGE_KEY: 87}),
                                  ("Praha_server", {CHARGE_KEY: 64})]
    assert [name for name, _ in sender.sent] == ["TG1", "TG1"]


def test_the_server_reports_its_own_state_every_cycle():
    """UC7-R4: the host of the server gets its state of the agent, like a turbine."""
    sender = FakeSender()
    agent, _ = make_agent(sender=sender, ups=FakeUps(), server=watched_server(), cycles=2)

    agent.run()

    assert sender.server_states == [("Praha_server", {STATUS_KEY: OK, ERROR_KEY: ""})] * 2
    assert agent.server_status == OK


def test_the_server_host_gets_only_the_metrics_of_its_catalog():
    """UC3-R1: nothing reaches the host of the server that its table does not hold."""
    sender = FakeSender()
    agent, _ = make_agent(sender=sender, ups=FakeUps(), server=watched_server(), cycles=1)

    agent.run()

    sent = {key for _, values in sender.server_sent + sender.server_states
            for key in values}
    assert sent == set(metrics.SERVER_KEYS)


def test_a_ups_that_is_not_watched_is_neither_read_nor_reported():
    """UC7-R1: with the UPS switched off the agent works as it did before UC7."""
    sender = FakeSender()
    ups = FakeUps()
    agent, _ = make_agent(sender=sender, ups=ups, server=ServerConfig(), cycles=2)

    agent.run()

    assert ups.reads == 0
    assert sender.server_sent == [] and sender.server_states == []
    assert len(sender.sent) == 2


def test_a_failed_read_of_ipp_is_an_error_on_the_server_host():
    """UC7-R3: state 2 with the text of the error, and no charge in that cycle."""
    sender = FakeSender()
    agent, _ = make_agent(sender=sender, ups=FakeUps(fail_on=[1]), server=watched_server(),
                          cycles=1)

    agent.run()

    assert sender.server_sent == []
    assert sender.server_states[0][1][STATUS_KEY] == ERROR
    assert "cannot be reached" in sender.server_states[0][1][ERROR_KEY]
    assert agent.server_status == ERROR


def test_a_failed_read_of_ipp_is_written_to_the_log(written_records):
    """UC7-R3: the error is in the log file too."""
    agent, _ = make_agent(ups=FakeUps(fail_on=[1]), server=watched_server(), cycles=1)

    agent.run()

    assert any(record.levelno == logging.ERROR and "cannot be reached" in record.getMessage()
               for record in written_records)


def test_the_charge_comes_back_once_ipp_does():
    """UC7-R3: the next cycle after the fault sends the charge again, without a restart."""
    sender = FakeSender()
    agent, _ = make_agent(sender=sender, ups=FakeUps(charges=[87], fail_on=[1]),
                          server=watched_server(), cycles=2)

    agent.run()

    assert sender.server_sent == [("Praha_server", {CHARGE_KEY: 87})]
    assert [values[STATUS_KEY] for _, values in sender.server_states] == [ERROR, OK]
    assert sender.server_states[-1][1][ERROR_KEY] == ""


def test_a_failed_read_of_ipp_leaves_the_turbines_alone():
    """UC7-R4: the turbines keep sending, and say nothing about IPP."""
    sender = FakeSender()
    agent, _ = make_agent(sender=sender, ups=FakeUps(fail_on=[1, 2]),
                          server=watched_server(), cycles=2)

    agent.run()

    assert len(sender.sent) == 2
    assert [values for _, values in sender.states] == [{STATUS_KEY: OK, ERROR_KEY: ""}] * 2
    assert agent.status == OK


def test_a_database_that_is_away_leaves_the_server_alone():
    """UC7-R4: the charge is still sent, and the server host says nothing about MySQL."""
    sender = FakeSender()
    agent, _ = make_agent(collector=FakeCollector(fail_on=[1, 2]), sender=sender,
                          ups=FakeUps(), server=watched_server(), cycles=2)

    agent.run()

    assert len(sender.server_sent) == 2
    assert [values for _, values in sender.server_states] == \
        [{STATUS_KEY: OK, ERROR_KEY: ""}] * 2
    assert agent.status == ERROR


def test_an_unreachable_zabbix_is_not_reported_on_the_server_host():
    """UC7-R4: like for a turbine, an outage of Zabbix is not reported at all."""
    sender = FakeSender(server_unreachable_on=[1])
    agent, _ = make_agent(sender=sender, ups=FakeUps(), server=watched_server(), cycles=1)

    agent.run()

    assert sender.server_states == []
    assert agent.server_status == OK


def test_an_outage_of_zabbix_is_counted_once_per_cycle():
    """UC5-R3: a cycle that did not get through counts once, however many hosts it has."""
    sender = FakeSender(unreachable_on=[1, 2], server_unreachable_on=[1, 2])
    agent, _ = make_agent(sender=sender, ups=FakeUps(), server=watched_server(), cycles=2)

    agent.run()

    assert agent.failed_sends == 2


def test_an_outage_seen_only_by_the_server_is_counted_too():
    """UC5-R3: values of the server that never arrived are values that never arrived."""
    sender = FakeSender(server_unreachable_on=[1])
    agent, _ = make_agent(sender=sender, ups=FakeUps(), server=watched_server(), cycles=1)

    agent.run()

    assert agent.failed_sends == 1


def test_a_charge_rejected_by_zabbix_is_an_error_on_the_server_host():
    """UC7-R4: a server host Zabbix does not know is a fault somebody has to fix."""
    sender = FakeSender(server_fail_on=[1])
    agent, _ = make_agent(sender=sender, ups=FakeUps(), server=watched_server(), cycles=1)

    agent.run()

    assert agent.server_status == ERROR
    assert "Praha_server" in sender.server_states[0][1][ERROR_KEY]


def test_the_agent_reads_ipp_itself_when_the_ups_is_watched():
    """UC7-R2: an agent built from the configuration talks to IPP on its own."""
    config = Config(zabbix=ZabbixConfig(location="Praha"),
                    turbines=[Turbine(name="TG1", system_id=11)],
                    server=watched_server())

    agent = Agent(config, collector=FakeCollector(), sender=FakeSender())

    assert isinstance(agent.ups, IppClient)


def test_the_agent_leaves_ipp_alone_when_the_ups_is_not_watched():
    config = Config(zabbix=ZabbixConfig(location="Praha"),
                    turbines=[Turbine(name="TG1", system_id=11)])

    agent = Agent(config, collector=FakeCollector(), sender=FakeSender())

    assert agent.ups is None
