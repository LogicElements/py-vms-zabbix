"""The measurement loop: collect the values of every turbine and of the server, send
them to Zabbix, report how the cycle went, wait, repeat.

An error in one cycle must not end the loop. The database is unreachable, Zabbix is
down, a turbine has no row - the cycle is given up, the state of the agent says so,
and the next cycle starts five seconds later and picks up again once the cause is
gone.

The turbines and the server are two parts of the cycle that do not share a fault: the
server host reports only what went wrong reading the server, the turbine hosts only
what went wrong reading the database.
"""

from __future__ import annotations

import time

from zabbixvms.collector import Collector
from zabbixvms.config import DEFAULT_PERIOD, Config
from zabbixvms.log import log
from zabbixvms.sender import TrapperSender, ZabbixUnreachable
from zabbixvms.ups import IppClient

# Delay between the end of one measurement cycle and the start of the next; it comes
# from the configuration, this is what an agent without one would wait.
CYCLE_DELAY = DEFAULT_PERIOD

# Values of vms.agent_status.
OK = 0
WARNING = 1
ERROR = 2

# vms.agent_error is a Character item, which holds 255 characters.
MAX_ERROR_LENGTH = 255

STATUS_KEY = "vms.agent_status"
ERROR_KEY = "vms.agent_error"
CHARGE_KEY = "ups.charge"

# How many cycles in a row may fail to reach Zabbix before the log says so. A blip is
# worth nothing to anybody: the report of it could only travel once the connection is
# back, by which time it describes something that is over. Zabbix sees a real outage as
# a host that went quiet, which is what the trigger on missing data is for.
TOLERATED_SEND_FAILURES = 5


class Agent:
    """Runs the measurement cycle over all turbines of the configuration and over
    the server, when the configuration watches its UPS."""

    def __init__(self, config: Config, collector: Collector | None = None,
                 sender: TrapperSender | None = None, sleep=time.sleep,
                 ups: IppClient | None = None) -> None:
        self._config = config
        self._collector = collector if collector is not None else Collector(config.database)
        self._sender = sender if sender is not None else TrapperSender(config.zabbix)
        self._sleep = sleep
        self._running = False
        self._warnings: list[str] = []
        # Reads the UPS of the server; None while the configuration does not watch it.
        self.ups = None
        if config.server.ups.enabled:
            self.ups = ups if ups is not None else IppClient(config.server.ups)
        # Error of the last cycle, or None when the last cycle went through.
        self.last_error: Exception | None = None
        # Cycles in a row whose values did not reach Zabbix; zero once one gets there.
        self.failed_sends = 0
        # What the agent said about itself in the last cycle, on the turbine hosts.
        self.status = OK
        self.error_text = ""
        # The same for the host of the server.
        self.server_last_error: Exception | None = None
        self.server_status = OK
        self.server_error_text = ""

    @property
    def running(self) -> bool:
        return self._running

    @property
    def period(self) -> int:
        """Seconds waited between cycles, as the configuration sets them."""
        return self._config.zabbix.period

    def cycle(self) -> None:
        """One measurement cycle: every turbine collected and sent."""
        self._warnings = []
        if not self._collector.is_connected:
            self._collector.connect()
        for turbine in self._config.turbines:
            values = self._collector.collect(turbine)
            self._warnings.extend(self._collector.warnings)
            self._sender.send(turbine, values)

    def server_cycle(self) -> None:
        """The values of the server read and sent to its host."""
        self._sender.send_to(self._config.server.host, {CHARGE_KEY: self.ups.charge()})

    def run(self) -> None:
        """Repeat the cycle until stop() is called."""
        self._running = True
        while self._running:
            outcomes = [self._run_turbines()]
            if self.ups is not None:
                outcomes.append(self._run_server())
            unreachable = [outcome for outcome in outcomes
                           if isinstance(outcome, ZabbixUnreachable)]
            if unreachable:
                self._tolerate_unreachable(unreachable[0])
            elif any(outcome is True for outcome in outcomes):
                self._forget_unreachable()
            self._sleep(self.period)

    def _run_turbines(self):
        """The part of the cycle for the turbines, with the state it ends in reported.

        Returns True when the values got to Zabbix, the ZabbixUnreachable that kept
        them away, or False when the cycle failed before it could tell.
        """
        try:
            self.cycle()
            self.last_error = None
            status, message = self._state_of_the_cycle()
        except ZabbixUnreachable as err:
            return err
        except Exception as err:
            # The loop outlives the cycle; the database or Zabbix may come back.
            self.last_error = err
            status, message = ERROR, str(err)
            log.error("measurement cycle failed: %s", err)
            self._collector.close()
        self.status = status
        self.error_text = message[:MAX_ERROR_LENGTH]
        self.report_state()
        return status != ERROR

    def _run_server(self):
        """The part of the cycle for the server, answering like _run_turbines()."""
        try:
            self.server_cycle()
            self.server_last_error = None
            status, message = OK, ""
        except ZabbixUnreachable as err:
            return err
        except Exception as err:
            self.server_last_error = err
            status, message = ERROR, str(err)
            log.error("reading the server failed: %s", err)
        self.server_status = status
        self.server_error_text = message[:MAX_ERROR_LENGTH]
        self._report_server_state()
        return status != ERROR

    def _tolerate_unreachable(self, err: Exception) -> None:
        """Count a cycle whose values never arrived, and say nothing to Zabbix.

        Saying anything is impossible anyway while the connection is down, and once it
        is up the news is stale. The database connection stays open: it is not the one
        that broke.
        """
        self.failed_sends += 1
        if self.failed_sends == TOLERATED_SEND_FAILURES:
            log.error("values have not reached Zabbix in %d cycles in a row: %s",
                      self.failed_sends, err)

    def _forget_unreachable(self) -> None:
        """Note that the values are getting through again and start counting afresh."""
        if self.failed_sends >= TOLERATED_SEND_FAILURES:
            log.info("values are reaching Zabbix again after %d cycles",
                     self.failed_sends)
        self.failed_sends = 0

    def stop(self) -> None:
        """Ask the loop to finish and release the database connection."""
        self._running = False
        self._collector.close()

    def report_state(self) -> None:
        """Send how the agent is doing to the host of every turbine.

        The state goes out even when the cycle failed, so the operator sees why no
        values arrived. When Zabbix is the thing that is down, this cannot get
        through either and is only written to the log.
        """
        values = {STATUS_KEY: self.status, ERROR_KEY: self.error_text}
        for turbine in self._config.turbines:
            try:
                self._sender.send(turbine, values)
            except Exception as err:
                log.error("state of the agent could not be sent for turbine %s: %s",
                          turbine.name, err)

    def _report_server_state(self) -> None:
        """Send how reading the server went to its host, like report_state()."""
        values = {STATUS_KEY: self.server_status, ERROR_KEY: self.server_error_text}
        try:
            self._sender.send_to(self._config.server.host, values)
        except Exception as err:
            log.error("state of the agent could not be sent for the server %s: %s",
                      self._config.server.host, err)

    def _state_of_the_cycle(self) -> tuple[int, str]:
        """Status and text after a cycle that got through without an exception."""
        if not self._warnings:
            return OK, ""
        message = "; ".join(self._warnings)
        log.warning("measurement cycle finished with a warning: %s", message)
        return WARNING, message
