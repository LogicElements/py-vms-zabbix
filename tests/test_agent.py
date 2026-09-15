"""Tests of the measurement loop against faked objects: every turbine of the
configuration, the delay between cycles and surviving a failed cycle
(UC1-R4, UC4-R6)."""

import logging

import pytest

from zabbixvms.log import log as agent_log
from zabbixvms.agent import (
    CYCLE_DELAY,
    ERROR,
    ERROR_KEY,
    MAX_ERROR_LENGTH,
    OK,
    STATUS_KEY,
    WARNING,
    Agent,
)
from zabbixvms.config import Config, Turbine, ZabbixConfig


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

    def __init__(self, fail_on=(), fail_state=False):
        self.fail_on = set(fail_on)
        self.fail_state = fail_state
        self.sent = []
        self.states = []

    def send(self, turbine, values):
        if STATUS_KEY in values:
            self.states.append((turbine.name, values))
            if self.fail_state:
                raise RuntimeError("Zabbix is away")
            return
        self.sent.append((turbine.name, values))
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


def make_agent(turbines=None, collector=None, sender=None, cycles=2):
    config = Config(
        zabbix=ZabbixConfig(location="Praha"),
        turbines=turbines if turbines is not None else [Turbine(name="TG1", system_id=11)],
    )
    holder = []
    clock = FakeClock(holder, cycles=cycles)
    agent = Agent(
        config,
        collector=collector if collector is not None else FakeCollector(),
        sender=sender if sender is not None else FakeSender(),
        sleep=clock,
    )
    holder.append(agent)
    return agent, clock


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
    """UC4-R6: five seconds pass between the cycles."""
    agent, clock = make_agent(cycles=3)

    agent.run()

    assert clock.delays == [CYCLE_DELAY, CYCLE_DELAY, CYCLE_DELAY]
    assert CYCLE_DELAY == 5


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
