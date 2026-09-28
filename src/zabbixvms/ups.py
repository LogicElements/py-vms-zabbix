"""Reads the charge of the UPS of the server from Eaton Intelligent Power Protector.

IPP has no documented interface. The agent talks to the services the web page of
IPP 1.73 calls from the browser, each a POST of a form to
`<url>/server/<service>?action=<action>` that answers with JSON:

- user_srv.js queryLoginChallenge and loginUser log in and give a session,
- data_srv.js getNodeData lists the power sources with their tags,
- data_srv.js loadNodeData holds the current values of the nodes asked for.

IPP shows a UPS on USB and one on the network the same way, so how the UPS is
connected makes no difference here.
"""

from __future__ import annotations

import hashlib
import hmac
import http.client
import json
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request

from zabbixvms.config import UpsConfig

# Seconds one request to IPP may take; IPP answers on the server itself, so anything
# longer is an IPP that hangs, and the cycle of the turbines waits for it.
TIMEOUT = 10

# What the page asks for when it lists the power sources; the UPS among them carry
# UPS in their tags.
POWER_SOURCES = json.dumps([{"viewID": "nodePowerComponentPortalPanel",
                             "object": "System.Tag", "op": "==", "value": "PWS"}])
NODE_FIELDS = json.dumps(["nodeID", "System.Tag"])
UPS_TAG = "UPS"

CHARGE = "UPS.PowerSummary.RemainingCapacity"
COMMUNICATION_LOST = "System.CommunicationLost"

# The session the page sends before it has one.
NO_SESSION = "0"


class IppError(Exception):
    """IPP could not tell the charge of the UPS."""


class CommunicationLost(IppError):
    """IPP answers, but it lost the UPS; the session is not what is wrong."""


class IppUnreachable(IppError):
    """No answer came from IPP at all; a new login would get none either."""


def encode_password(password: str, challenge: str) -> str:
    """The password as loginUser takes it, the way user_settings.js of IPP builds it.

    HMAC-SHA1 over the challenge, keyed by the SHA1 of the password written in hex.
    IPP's own SHA1 reads the characters of the text, which agrees with SHA1 of its
    bytes only for ASCII; the configuration refuses any other password.
    """
    key = hashlib.sha1(password.encode("ascii")).hexdigest().encode("ascii")
    return hmac.new(key, challenge.encode("ascii"), hashlib.sha1).hexdigest()


def _connect_ipv4_first(address, timeout=socket._GLOBAL_DEFAULT_TIMEOUT,
                        source_address=None) -> socket.socket:
    """socket.create_connection() trying the IPv4 addresses of the name first.

    IPP 1.73 listens on 0.0.0.0 only, and Windows on the server gives localhost as ::1
    first. Being refused on ::1 takes Windows two seconds, which every request to IPP
    paid before 127.0.0.1 was tried.
    """
    host, port = address
    found = socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM)
    ordered = sorted(found, key=lambda info: info[0] != socket.AF_INET)
    error = OSError(f"{host} has no address")
    for *_, sockaddr in ordered:
        try:
            return socket.create_connection((sockaddr[0], port), timeout, source_address)
        except OSError as err:
            error = err
    raise error


class _HTTPConnection(http.client.HTTPConnection):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._create_connection = _connect_ipv4_first


class _HTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._create_connection = _connect_ipv4_first


class _HTTPHandler(urllib.request.HTTPHandler):
    def http_open(self, req):
        return self.do_open(_HTTPConnection, req)


class _HTTPSHandler(urllib.request.HTTPSHandler):
    def https_open(self, req):
        return self.do_open(_HTTPSConnection, req, context=self._context)


def _unverified_context() -> ssl.SSLContext:
    """TLS without checking the certificate: IPP serves a self-signed one of its own,
    and the connection never leaves the server."""
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


class IppClient:
    """Logs in to IPP like its web page does and reads the charge of its UPS."""

    def __init__(self, ups: UpsConfig, timeout: float = TIMEOUT) -> None:
        self._ups = ups
        self._timeout = timeout
        self._session: str | None = None
        self.ssl_context = _unverified_context()
        # IPP answers on the server itself; a proxy set for the machine, from the
        # environment or the registry, does not know it and must not be asked.
        self._opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), _HTTPHandler(),
            _HTTPSHandler(context=self.ssl_context))

    def charge(self) -> int:
        """Charge in % of the UPS that is worst off among those IPP manages.

        The session of an earlier cycle is used as long as IPP takes it. How IPP turns
        down a session that expired is not known, so a failed read on a kept session
        is answered by one new login and the read once more; what fails after that is
        reported. A UPS IPP lost is no reason to log in again, and neither is an IPP
        that does not answer at all: the login would only wait for it a second time.
        """
        if self._session is not None:
            try:
                return self._read_charge()
            except (CommunicationLost, IppUnreachable):
                raise
            except IppError:
                self._session = None
        self._login()
        return self._read_charge()

    def _login(self) -> None:
        challenge = self._call("user_srv.js", "queryLoginChallenge").get("challenge")
        if not isinstance(challenge, str) or not challenge:
            raise IppError("IPP answered queryLoginChallenge without a challenge")
        answer = self._call("user_srv.js", "loginUser", {
            "login": self._ups.login,
            "password": encode_password(self._ups.password, challenge),
        })
        session = answer.get("sessionID")
        if answer.get("success") is not True or not session:
            raise IppError(f"IPP turned down the login of user {self._ups.login!r}")
        self._session = str(session)

    def _read_charge(self) -> int:
        listed = self._call("data_srv.js", "getNodeData",
                            {"filter": POWER_SOURCES, "fieldSet": NODE_FIELDS}).get("data")
        if not isinstance(listed, list):
            raise IppError("IPP answered getNodeData without a list of nodes")
        ups_ids = [str(node.get("nodeID")) for node in listed
                   if isinstance(node, dict) and self._is_ups(node)]
        if not ups_ids:
            raise IppError("IPP manages no UPS")

        nodes = self._call("data_srv.js", "loadNodeData",
                           {"nodes": json.dumps(ups_ids)}).get("nodeData")
        if not isinstance(nodes, dict):
            raise IppError("IPP answered loadNodeData without the data of the nodes")
        return min(self._charge_of(node_id, nodes.get(node_id)) for node_id in ups_ids)

    @staticmethod
    def _is_ups(node: dict) -> bool:
        tags = node.get("System.Tag")
        return isinstance(tags, str) and UPS_TAG in tags.split(",")

    @staticmethod
    def _charge_of(node_id: str, node) -> int:
        if not isinstance(node, dict):
            raise IppError(f"IPP answered loadNodeData without UPS {node_id}")
        if node.get(COMMUNICATION_LOST) == 1:
            raise CommunicationLost(f"IPP lost the communication with UPS {node_id}")
        charge = node.get(CHARGE)
        if isinstance(charge, bool) or not isinstance(charge, (int, float)):
            raise IppError(f"IPP gave UPS {node_id} no number in {CHARGE}: {charge!r}")
        return round(charge)

    def _call(self, service: str, action: str, form: dict | None = None) -> dict:
        """POST one form to a service of IPP and return its JSON answer."""
        url = f"{self._ups.url.rstrip('/')}/server/{service}?action={action}"
        fields = dict(form or {})
        fields["sessionID"] = self._session if self._session is not None else NO_SESSION
        headers = {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"}
        if self._session is not None:
            # IPP 1.73 serves the data services only with the session in the cookie the
            # page sets after the login; the form field alone gets the connection closed.
            headers["Cookie"] = f"sessionID={self._session}"
        request = urllib.request.Request(
            url, data=urllib.parse.urlencode(fields).encode("ascii"), headers=headers)
        try:
            with self._opener.open(request, timeout=self._timeout) as response:
                body = response.read()
        except urllib.error.HTTPError as err:
            raise IppError(f"IPP answered {action} with HTTP {err.code}") from err
        except http.client.RemoteDisconnected as err:
            # The request got there and IPP closed the connection instead of answering,
            # which is how it turns down a request without a session it knows. It is not
            # an IPP that is away, so a new login may well help.
            raise IppError(f"IPP closed the connection without answering {action}") from err
        except (urllib.error.URLError, OSError, http.client.HTTPException) as err:
            reason = getattr(err, "reason", err)
            raise IppUnreachable(
                f"IPP at {self._ups.url} cannot be reached: {reason}") from err
        try:
            answer = json.loads(body.decode("utf-8"))
        except ValueError as err:
            raise IppError(f"IPP answered {action} with something else than JSON") from err
        if not isinstance(answer, dict):
            raise IppError(f"IPP answered {action} with something else than an object")
        return answer
