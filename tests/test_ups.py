"""Tests of reading the charge of the UPS from Eaton IPP against a faked IPP served
over HTTP: the login of its web page, the session kept between cycles, the lowest
charge over its UPS and the errors that leave the charge unknown (UC7-R2, UC7-R3).

The answers of the data services are the ones IPP 1.73 gave its browser page, kept in
tests/data/ipp. The login answers were not recorded; their shape is what the page's
user_settings.js reads out of them, and matches the lengths IPP reported for them.
"""

import copy
import json
import socket
import ssl
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from zabbixvms.config import UpsConfig
from zabbixvms.ups import IppClient, IppError, encode_password

DATA = Path(__file__).resolve().parent / "data" / "ipp"
NODE_ID = "GA10R14030"
PASSWORD = "Vms2015"


def recorded(action):
    return json.loads((DATA / f"{action}.json").read_text(encoding="utf-8"))


class FakeIpp:
    """The services of IPP the agent talks to, answering the way IPP 1.73 does."""

    def __init__(self):
        self.challenges = iter(f"{index:040x}" for index in range(1, 1000))
        self.challenge = None
        self.sessions = set()
        self.requests = []
        self.node_list = recorded("getNodeData")
        self.node_data = recorded("loadNodeData")
        # What a data service answers to a session it does not know; how IPP really
        # answers is not recorded, so the quietest plausible answer is the default.
        self.stale_answer = {"data": [], "nodeData": {}}
        self.broken = {}
        self.delay = 0

    def add_ups(self, node_id, charge, tag="DEV,UPS,SDN,PWS"):
        """Put another power source beside the recorded UPS."""
        self.node_list["data"].append({"nodeID": node_id, "System.Tag": tag})
        node = copy.deepcopy(self.node_data["nodeData"][NODE_ID])
        node["System.Tag"] = tag
        node["UPS.PowerSummary.RemainingCapacity"] = charge
        self.node_data["nodeData"][node_id] = node

    def node(self, node_id=NODE_ID):
        return self.node_data["nodeData"][node_id]

    def expire_sessions(self):
        self.sessions.clear()

    def logins(self):
        return [form for action, form in self.requests if action == "loginUser"]

    def answer(self, action, form):
        """Body of the answer, as text, to one request of the page."""
        self.requests.append((action, form))
        if action in self.broken:
            return self.broken[action]
        if action == "queryLoginChallenge":
            self.challenge = next(self.challenges)
            return json.dumps({"challenge": self.challenge})
        if action == "loginUser":
            if form.get("login") == "admin" and \
                    form.get("password") == encode_password(PASSWORD, self.challenge):
                session = f"{len(self.requests):040x}"
                self.sessions.add(session)
                return json.dumps({"success": True, "sessionID": session, "maxAge": 900,
                                   "passwordMustBeChanged": False})
            return json.dumps({"success": False})
        if form.get("sessionID") not in self.sessions:
            if isinstance(self.stale_answer, int):
                return self.stale_answer
            return json.dumps(self.stale_answer)
        if action == "getNodeData":
            return json.dumps(self.node_list)
        if action == "loadNodeData":
            asked = json.loads(form["nodes"])
            return json.dumps({"nodeData": {node_id: data for node_id, data
                                            in self.node_data["nodeData"].items()
                                            if node_id in asked}})
        raise AssertionError(f"the agent has no business calling {action}")


@pytest.fixture
def ipp():
    """A faked IPP listening on a free port of this machine."""
    fake = FakeIpp()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            path, _, query = self.path.partition("?")
            action = urllib.parse.parse_qs(query)["action"][0]
            length = int(self.headers["Content-Length"])
            form = dict(urllib.parse.parse_qsl(self.rfile.read(length).decode("utf-8")))
            form["_service"] = path
            time.sleep(fake.delay)
            answer = fake.answer(action, form)
            if isinstance(answer, int):
                self.send_error(answer)
                return
            body = answer.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/x-javascript; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    # A short poll keeps the shutdown after each test from waiting half a second.
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.02},
                              daemon=True)
    thread.start()
    fake.url = f"http://127.0.0.1:{server.server_address[1]}"
    yield fake
    server.shutdown()
    server.server_close()


def client_of(ipp, password=PASSWORD, **kwargs):
    return IppClient(UpsConfig(enabled=True, url=ipp.url, login="admin",
                               password=password), **kwargs)


def test_the_password_is_hashed_the_way_the_page_of_ipp_does():
    """UC7-R2: HMAC-SHA1 keyed by the SHA1 of the password in hex, over the challenge.

    The expected values were computed by SHA1 and HMAC of IPP's own libs/utils.js,
    run under Windows Script Host.
    """
    assert encode_password("admin", "0123456789abcdef") == \
        "be4a6371f71278de2e63b68fdbd25d01234bd7ac"
    assert encode_password("Vms2015", "c2VjcmV0LWNoYWxsZW5nZQ==") == \
        "39fb1c19ecf03d02ccf9f48bd96ab33045a38b0a"


def test_the_charge_is_the_remaining_capacity_of_the_ups(ipp):
    """UC7-R2: ups.charge is UPS.PowerSummary.RemainingCapacity."""
    ipp.node()["UPS.PowerSummary.RemainingCapacity"] = 87

    assert client_of(ipp).charge() == 87


def test_the_recorded_ups_is_fully_charged(ipp):
    """What IPP 1.73 reported for the UPS on USB when it was recorded."""
    assert client_of(ipp).charge() == 100


def test_the_agent_logs_in_the_way_the_page_of_ipp_does(ipp):
    """UC7-R2: a challenge first, then the login with the password hashed over it."""
    client_of(ipp).charge()

    actions = [action for action, _ in ipp.requests]
    assert actions[:2] == ["queryLoginChallenge", "loginUser"]
    challenge_request, login = ipp.requests[0][1], ipp.requests[1][1]
    assert challenge_request["_service"] == "/server/user_srv.js"
    assert login["_service"] == "/server/user_srv.js"
    assert login["login"] == "admin"
    assert login["password"] == encode_password(PASSWORD, f"{1:040x}")
    assert PASSWORD not in json.dumps(ipp.requests)


def test_the_ups_are_found_and_read_with_the_session(ipp):
    """UC7-R2: the power sources are listed, then their data read, both in a session."""
    client_of(ipp).charge()

    reads = ipp.requests[2:]
    assert [(form["_service"], action) for action, form in reads] == [
        ("/server/data_srv.js", "getNodeData"), ("/server/data_srv.js", "loadNodeData")]
    assert all(form["sessionID"] in ipp.sessions for _, form in reads)
    assert json.loads(reads[1][1]["nodes"]) == [NODE_ID]


def test_the_session_is_kept_between_cycles(ipp):
    """UC7-R2: one login serves every cycle while IPP takes the session."""
    client = client_of(ipp)

    for _ in range(3):
        client.charge()

    assert len(ipp.logins()) == 1


def test_a_session_ipp_turned_down_is_replaced_in_the_same_cycle(ipp):
    """UC7-R2: the agent logs in again once and still reads the charge in that cycle."""
    client = client_of(ipp)
    client.charge()
    ipp.expire_sessions()
    ipp.node()["UPS.PowerSummary.RemainingCapacity"] = 64

    assert client.charge() == 64
    assert len(ipp.logins()) == 2


def test_a_session_turned_down_with_an_http_error_is_replaced_too(ipp):
    """UC7-R2: however IPP says no to the session, one new login follows."""
    client = client_of(ipp)
    client.charge()
    ipp.expire_sessions()
    ipp.stale_answer = 403

    assert client.charge() == 100
    assert len(ipp.logins()) == 2


def test_a_read_that_fails_after_a_new_login_is_not_tried_a_third_time(ipp):
    """UC7-R3: one new login per cycle; what still fails then is reported."""
    client = client_of(ipp)
    client.charge()
    ipp.broken["getNodeData"] = 500

    with pytest.raises(IppError):
        client.charge()

    assert len(ipp.logins()) == 2


def test_the_lowest_charge_of_several_ups_is_reported(ipp):
    """UC7-R2: with more UPS the one that is worst off is what counts."""
    ipp.add_ups("GA10R99999", 42)

    assert client_of(ipp).charge() == 42


def test_a_power_source_that_is_not_a_ups_does_not_count(ipp):
    """UC7-R2: only nodes with UPS among their tags are UPS."""
    ipp.add_ups("PDU0001", 3, tag="DEV,PDU,PWS")

    assert client_of(ipp).charge() == 100


def test_an_ipp_that_is_not_there_is_an_error():
    """UC7-R3: nothing listens where IPP should be."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    # Windows retries a refused connection for two seconds before it gives up.
    client = IppClient(UpsConfig(enabled=True, url=f"http://127.0.0.1:{port}",
                                 password=PASSWORD), timeout=0.5)

    with pytest.raises(IppError, match="cannot be reached"):
        client.charge()


def test_an_ipp_that_does_not_answer_in_time_is_an_error(ipp):
    """UC7-R3: a hanging IPP must not hold up the cycle of the turbines."""
    ipp.delay = 1

    with pytest.raises(IppError):
        client_of(ipp, timeout=0.2).charge()


def test_a_rejected_login_is_an_error(ipp):
    """UC7-R3: a wrong password is said so, not taken for a missing UPS."""
    with pytest.raises(IppError, match="login"):
        client_of(ipp, password="wrong").charge()


def test_an_answer_that_is_not_json_is_an_error(ipp):
    """UC7-R3: an answer in an unexpected shape."""
    ipp.broken["loadNodeData"] = "<html>Service Unavailable</html>"

    with pytest.raises(IppError, match="loadNodeData"):
        client_of(ipp).charge()


def test_an_answer_without_the_charge_is_an_error(ipp):
    """UC7-R3: an answer in an unexpected shape, as JSON."""
    del ipp.node()["UPS.PowerSummary.RemainingCapacity"]

    with pytest.raises(IppError, match="RemainingCapacity"):
        client_of(ipp).charge()


def test_a_charge_that_is_not_a_number_is_an_error(ipp):
    ipp.node()["UPS.PowerSummary.RemainingCapacity"] = "100"

    with pytest.raises(IppError, match="RemainingCapacity"):
        client_of(ipp).charge()


def test_an_http_error_is_an_error(ipp):
    ipp.broken["getNodeData"] = 500

    with pytest.raises(IppError):
        client_of(ipp).charge()


def test_an_ipp_without_a_ups_is_an_error(ipp):
    """UC7-R3: nothing to read the charge of."""
    ipp.node_list["data"] = []

    with pytest.raises(IppError, match="no UPS"):
        client_of(ipp).charge()


def test_a_ups_ipp_lost_the_communication_with_is_an_error(ipp):
    """UC7-R3: the value IPP still holds is the last it heard, not the charge now."""
    ipp.node()["System.CommunicationLost"] = 1

    with pytest.raises(IppError, match="communication"):
        client_of(ipp).charge()


def test_a_lost_communication_keeps_the_session(ipp):
    """UC7-R2: the session is fine, it is the UPS IPP cannot reach; no new login."""
    client = client_of(ipp)
    client.charge()
    ipp.node()["System.CommunicationLost"] = 1

    with pytest.raises(IppError):
        client.charge()

    assert len(ipp.logins()) == 1


def test_the_charge_is_read_again_once_the_cause_is_gone(ipp):
    """UC7-R3: the next cycle after the fault reads the charge without a restart."""
    client = client_of(ipp)
    ipp.broken["loginUser"] = 500
    with pytest.raises(IppError):
        client.charge()

    del ipp.broken["loginUser"]

    assert client.charge() == 100


def test_the_certificate_of_ipp_is_not_checked():
    """UC7-R2: IPP serves a self-signed certificate of its own."""
    context = IppClient(UpsConfig(enabled=True, password=PASSWORD)).ssl_context

    assert context.verify_mode == ssl.CERT_NONE
    assert context.check_hostname is False
