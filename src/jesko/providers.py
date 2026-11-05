from __future__ import annotations

import base64
import re
from urllib import request
from urllib.parse import quote
from xml.sax.saxutils import escape


class ProviderError(Exception):
    pass


class Ntfy:
    def __init__(self, server, topic, token="", timeout=5):
        self.server, self.topic, self.token, self.timeout = server.rstrip("/"), topic, token, timeout

    def send(self, message, title="JESKO", priority="default", tags="computer"):
        if not self.topic:
            raise ProviderError("ntfy topic not configured")
        req = request.Request(
            f"{self.server}/{quote(self.topic)}",
            data=message.encode(),
            method="POST",
            headers={"Title": title, "Priority": priority, "Tags": tags, "Content-Type": "text/plain"},
        )
        if self.token:
            req.add_header("Authorization", "Bearer " + self.token)
        try:
            with request.urlopen(req, timeout=self.timeout) as r:
                if not 200 <= r.status < 300:
                    raise ProviderError(f"ntfy status {r.status}")
        except Exception as e:
            raise ProviderError("ntfy publish failed") from e


class Twilio:
    def __init__(self, enabled, sid, token, sender, destination, timeout=5):
        self.enabled, self.sid, self.token, self.sender, self.destination, self.timeout = (
            enabled,
            sid,
            token,
            sender,
            destination,
            timeout,
        )

    def twiml(self, message):
        return f"<Response><Say>{escape(message[:500])}</Say></Response>"

    def send(self, message):
        if not self.enabled:
            raise ProviderError("calls disabled")
        if not all(re.fullmatch(r"\+[1-9]\d{7,14}", x or "") for x in (self.sender, self.destination)):
            raise ProviderError("invalid E.164 configuration")
        url = f"https://api.twilio.com/2010-04-01/Accounts/{self.sid}/Calls.json"
        data = (
            __import__("urllib.parse")
            .parse.urlencode(
                {"To": self.destination, "From": self.sender, "Twiml": self.twiml(message), "TimeLimit": "30"}
            )
            .encode()
        )
        auth = base64.b64encode(f"{self.sid}:{self.token}".encode()).decode()
        req = request.Request(url, data=data, headers={"Authorization": "Basic " + auth}, method="POST")
        try:
            with request.urlopen(req, timeout=self.timeout) as r:
                if not 200 <= r.status < 300:
                    raise ProviderError("twilio status")
        except Exception as e:
            raise ProviderError("twilio call failed") from e

    def masked_destination(self):
        return (self.destination[:3] + "***" + self.destination[-2:]) if self.destination else "not configured"
