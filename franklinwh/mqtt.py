"""This is an MQTT shim.

When franklinwh removed the clientside mqtt interaction, they introduced an API that accepts the same payloads. This is a gateway to that API

The API is kinda wonky because I migrated it from a working implementation that interacted with mqtt directly, since I believe the payloads are the same"""

import typing
from franklinwh import DEFAULT_URL_BASE
import requests
import json
import zlib
import time

def to_hex(inp):
    return f"{inp:08X}"

class FranklinMqtt(object):
    def __init__(self, gatewayId: str, token: typing.Callable[[], str]):
        self.gatewayId = gatewayId
        # TODO(richo) Need a way to refresh this, maybe make it a lambda or something
        self.token = token
        self.snno = 0

    def next_snno(self):
        self.snno += 1
        return self.snno

    def get_status(self):
        payload = self._build_payload(203, {"opt":1, "refreshData":1})
        return self._send(payload)


    def _build_payload(self, ty, data):
        blob = json.dumps(data, separators=(',', ':')).encode('utf-8')
        # crc = to_hex(zlib.crc32(blob.encode("ascii")))
        crc = to_hex(zlib.crc32(blob))
        l = len(blob)
        ts = int(time.time())

        temp = json.dumps({"lang":"EN_US", "cmdType":ty,"equipNo": self.gatewayId,"type":0,"timeStamp":ts,"snno":self.next_snno(),"len":l,"crc":crc,"dataArea":"DATA"})
        # We do it this way because without a canonical way to generate JSON we can't risk reordering breaking the CRC.
        return temp.replace('"DATA"', blob.decode('utf-8'))

    def _send(self, payload):
        url = DEFAULT_URL_BASE + "hes-gateway/terminal/sendMqtt"
        params = { "gatewayId": self.gatewayId, "lang": "en_US" }
        headers = { "loginToken": self.token(), "Content-Type": "application/json" }
        res = requests.post(url, headers=headers, data=payload)

        json = res.json()
        assert(json['code'] == 200)
        return json
