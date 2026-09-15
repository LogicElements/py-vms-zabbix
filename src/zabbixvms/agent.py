"""The measurement loop: collect the values of every turbine, send them to Zabbix,
report how the cycle went, wait, repeat.

An error in one cycle must not end the loop. The database is unreachable, Zabbix is
down, a turbine has no row - the cycle is given up, the state of the agent says so,
and the next cycle starts five seconds later and picks up again once the cause is
gone.
"""

from __future__ import annotations

import time

from zabbixvms.collector import Collector
from zabbixvms.config import DEFAULT_PERIOD, Config
from zabbixvms.log import log
from zabbixvms.sender import TrapperSender

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


class Agent:
    """Runs the measurement cycle over all turbines of the configuration."""

    def __init__(self, config: Config, collector: Collector | None = None,
                 sender: TrapperSender | None = None, sleep=time.sleep) -> None:
        self._config = config
        self._collector = collector if collector is not None else Collector(config.database)
        self._sender = sender if sender is not None else TrapperSender(config.zabbix)
        self._sleep = sleep
        self._running = False
        self._warnings: list[str] = []
        # Error of the last cycle, or None when the last cycle went through.
        self.last_error: Exception | None = None
        # What the agent said about itself in the last cycle.
        self.status = OK
        self.error_text = ""

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

    def run(self) -> None:
        """Repeat the cycle until stop() is called."""
        self._running = True
        while self._running:
            try:
                self.cycle()
                self.last_error = None
                status, message = self._state_of_the_cycle()
            except Exception as err:
                # The loop outlives the cycle; the database or Zabbix may come back.
                self.last_error = err
                status, message = ERROR, str(err)
                log.error("measurement cycle failed: %s", err)
                self._collector.close()

            self.status = status
            self.error_text = message[:MAX_ERROR_LENGTH]
            self.report_state()
            self._sleep(self.period)

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

    def _state_of_the_cycle(self) -> tuple[int, str]:
        """Status and text after a cycle that got through without an exception."""
        if not self._warnings:
            return OK, ""
        message = "; ".join(self._warnings)
        log.warning("measurement cycle finished with a warning: %s", message)
        return WARNING, message
