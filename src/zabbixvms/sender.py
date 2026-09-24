"""Sends the collected values to Zabbix as trapper items.

One turbine is one Zabbix host, named `<location>_<turbine name>`, so the metrics of
different turbines and different locations never mix.
"""

from __future__ import annotations

from zabbix_utils import ItemValue, ProcessingError, Sender

from zabbixvms.config import Turbine, ZabbixConfig


class SenderError(Exception):
    """Zabbix did not accept the values that were sent."""


class ZabbixUnreachable(Exception):
    """The values never got to Zabbix: the exchange with the server itself failed.

    Kept apart from SenderError because the two call for opposite answers. Rejected
    values mean something is set up wrong and somebody has to be told; an exchange that
    did not happen means the network is having a moment, and the telling would arrive
    only once it is over.
    """


def host_name(location: str, turbine_name: str) -> str:
    """Name of the Zabbix host of one turbine: location and turbine joined by _."""
    return f"{location}_{turbine_name}"


class TrapperSender:
    """Sends metric values to the Zabbix trapper of the configured server."""

    def __init__(self, zabbix: ZabbixConfig, sender_factory=Sender) -> None:
        self._zabbix = zabbix
        self._sender = sender_factory(server=zabbix.server, port=zabbix.port)

    def host_name(self, turbine: Turbine) -> str:
        """Name of the Zabbix host the turbine's metrics are sent under."""
        return host_name(self._zabbix.location, turbine.name)

    def send(self, turbine: Turbine, values: dict[str, float]) -> None:
        """Send one turbine's values; raise SenderError for rejected values."""
        host = self.host_name(turbine)
        items = [ItemValue(host, key, str(value)) for key, value in values.items()]

        try:
            response = self._sender.send(items)
        except ProcessingError as err:
            # Everything the library reports this way is a failed exchange with the
            # server: no socket, no connection, a timeout, or an answer it cannot read.
            raise ZabbixUnreachable(str(err)) from err

        if response.failed:
            raise SenderError(
                f"Zabbix rejected {response.failed} of {len(items)} values "
                f"of host {host}"
            )
