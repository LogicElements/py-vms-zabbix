"""Tests of the measurement loop against faked objects: every turbine of the
configuration, the delay between cycles and surviving a failed cycle
(UC1-R4, UC4-R6)."""

import pytest

from zabbixvms.agent import CYCLE_DELAY, Agent
from zabbixvms.config import Config, Turbine, ZabbixConfig


class FakeCollector:
    def __init__(self, values=None, fail_on=()):
        self.values = values if values is not None else {"vms.speed": 1.0}
        self.fail_on = set(fail_on)
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
        if len(self.collected) in self.fail_on:
            raise RuntimeError("database is away")
        return dict(self.values)


class FakeSender:
    def __init__(self, fail_on=()):
        self.fail_on = set(fail_on)
        self.sent = []

    def send(self, turbine, values):
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
