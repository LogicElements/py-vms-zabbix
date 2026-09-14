"""The measurement loop: collect the values of every turbine, send them to Zabbix,
wait, repeat.

An error in one cycle must not end the loop. The database is unreachable, Zabbix is
down, a turbine has no row - the cycle is given up, the next one starts five seconds
later and picks up again once the cause is gone.
"""

from __future__ import annotations

import logging
import time

from zabbixvms.collector import Collector
from zabbixvms.config import Config
from zabbixvms.sender import TrapperSender

log = logging.getLogger(__name__)

# Delay between the end of one measurement cycle and the start of the next.
CYCLE_DELAY = 5


class Agent:
    """Runs the measurement cycle over all turbines of the configuration."""

    def __init__(self, config: Config, collector: Collector | None = None,
                 sender: TrapperSender | None = None, sleep=time.sleep) -> None:
        self._config = config
        self._collector = collector if collector is not None else Collector(config.database)
        self._sender = sender if sender is not None else TrapperSender(config.zabbix)
        self._sleep = sleep
        self._running = False
        # Error of the last cycle, or None when the last cycle went through.
        self.last_error: Exception | None = None

    @property
    def running(self) -> bool:
        return self._running

    def cycle(self) -> None:
        """One measurement cycle: every turbine collected and sent."""
        if not self._collector.is_connected:
            self._collector.connect()
        for turbine in self._config.turbines:
            values = self._collector.collect(turbine)
            self._sender.send(turbine, values)

    def run(self) -> None:
        """Repeat the cycle until stop() is called."""
        self._running = True
        while self._running:
            try:
                self.cycle()
                self.last_error = None
            except Exception as err:
                # The loop outlives the cycle; the database or Zabbix may come back.
                self.last_error = err
                log.exception("measurement cycle failed: %s", err)
                self._collector.close()
            self._sleep(CYCLE_DELAY)

    def stop(self) -> None:
        """Ask the loop to finish and release the database connection."""
        self._running = False
        self._collector.close()
