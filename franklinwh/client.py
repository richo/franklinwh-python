import json
import zlib
import time
import requests
import hashlib
from dataclasses import dataclass
import typing


from . import DEFAULT_URL_BASE

def to_hex(inp):
    return f"{inp:08X}"

@dataclass
class Current:
    solar_production: float
    generator_production: float
    battery_use: float
    grid_use: float
    home_load: float
    battery_soc: float

@dataclass
class Totals:
    battery_charge: float
    battery_discharge: float
    grid_import: float
    grid_export: float
    solar: float
    generator: float
    home_use: float

@dataclass
class Stats:
    current: Current
    totals: Totals


class TokenExpiredException(BaseException):
    """raised when the token has expired to signal upstream that you need to create a new client or inject a new token"""
    pass

class AccountLockedException(BaseException):
    pass

class InvalidCredentialsException(BaseException):
    pass

class DeviceTimeoutException(BaseException):
    pass

class TokenFetcher(object):
    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password

    def get_token(self):
        return TokenFetcher.login(self.username, self.password)

    @staticmethod
    def login(username: str, password: str):
        url = DEFAULT_URL_BASE + "hes-gateway/terminal/initialize/appUserOrInstallerLogin"
        hash = hashlib.md5(bytes(password, "ascii")).hexdigest()
        form = {
                "account": username,
                "password": hash,
                "lang": "en_US",
                "type": 1,
                }
        res = requests.post(url, data=form)
        json = res.json()

        if json['code'] == 401:
            raise InvalidCredentialsException(json['message'])

        if json['code'] == 400:
            raise AccountLockedException(json['message'])

        return json['result']['token']


def retry(func, fltr, refresh_func):
    """Tries calling func, and if filter fails it calls refresh func then tries again"""
    res = func()
    if fltr(res):
        return res
    refresh_func()
    return func()


class Client(object):
    def __init__(self, fetcher: TokenFetcher, gateway: str, url_base: str = DEFAULT_URL_BASE):
        self.fetcher = fetcher
        self.gateway = gateway
        self.url_base = url_base
        self.refresh_token()
        self.snno = 0

    def _post(self, url, payload):
        def __post():
            res = requests.post(url, headers={ "loginToken": self.token, "Content-Type": "application/json" }, data=payload).json()
            return res
        return retry(__post, lambda j: j['code'] != 401, self.refresh_token)

    def _get(self, url):
        params = { "gatewayId": self.gateway, "lang": "en_US" }
        def __get():
            return requests.get(url, params=params, headers={ "loginToken": self.token }).json()
        return retry(__get, lambda j: j['code'] != 401, self.refresh_token)


    def refresh_token(self):
        self.token = self.fetcher.get_token()

    def get_smart_switch_state(self):
        # TODO(richo) This API is super in flux, both because of how vague the
        # underlying API is and also trying to figure out what to do with
        # inconsistency.
        # Whether this should use the _switch_status() API is super unclear.
        # Maybe I will reach out to FranklinWH once I have published.
        status = self._status()
        switches = map(lambda x: x == 1, status["pro_load"])
        return tuple(switches)

    def set_smart_switch_state(self, state: (typing.Optional[bool], typing.Optional[bool], typing.Optional[bool])):
        """Set the state of the smart circuits

        Setting a value in the state tuple to True will turn on that circuit,
        setting to False will turn it off. Setting to None will make it
        unchanged.
        """

        payload = self._switch_status()
        payload["opt"] = 1
        payload.pop('modeChoose')
        payload.pop('result')

        if payload["SwMerge"] == 1:
            if state[0] != state[1]:
                raise RuntimeError("Smart switches 1 and 2 are merged! Setting them to different values could do bad things to your house. Aborting.")

        def set_value(keys, value):
            for k in keys:
                payload[k] = value


        for i in range(3):
            sw = i + 1
            mode = f"Sw{sw}Mode"
            msg_type = f"Sw{sw}MsgType"
            pro_load = f"Sw{sw}ProLoad"

            if state[i] is not None:
                payload[msg_type] = 1
                if state[i] == True:
                    payload[mode] = 1
                    payload[pro_load] = 0
                elif state[i] == False:
                    payload[mode] = 0
                    payload[pro_load] = 1

        print(payload)
        wire_payload = self._build_payload(311, payload)
        data = self._mqtt_send(wire_payload)['result']['dataArea']
        return json.loads(data)

    # Sends a 203 which is a high level status
    def _status(self):
        payload = self._build_payload(203, {"opt":1, "refreshData":1})
        data = self._mqtt_send(payload)['result']['dataArea']
        return json.loads(data)

    # Sends a 311 which appears to be a more specific switch command
    def _switch_status(self):
        payload = self._build_payload(311, {"opt":0, "order": self.gateway})
        data = self._mqtt_send(payload)['result']['dataArea']
        return json.loads(data)

    def get_stats(self) -> dict:
        """Get current statistics for the FHP.

        This includes instantaneous measurements for current power, as well as totals for today (in local time)
        """
        data = self._status()

        return Stats(
                Current(
                    data["p_sun"],
                    data["p_gen"],
                    data["p_fhp"],
                    data["p_uti"],
                    data["p_load"],
                    data["soc"]
                    ),
                Totals(
                    data["kwh_fhp_chg"],
                    data["kwh_fhp_di"],
                    data["kwh_uti_in"],
                    data["kwh_uti_out"],
                    data["kwh_sun"],
                    data["kwh_gen"],
                    data["kwh_load"]
                    ))

    def next_snno(self):
        self.snno += 1
        return self.snno


    def _build_payload(self, ty, data):
        blob = json.dumps(data, separators=(',', ':')).encode('utf-8')
        # crc = to_hex(zlib.crc32(blob.encode("ascii")))
        crc = to_hex(zlib.crc32(blob))
        l = len(blob)
        ts = int(time.time())

        temp = json.dumps({"lang":"EN_US", "cmdType":ty,"equipNo": self.gateway,"type":0,"timeStamp":ts,"snno":self.next_snno(),"len":l,"crc":crc,"dataArea":"DATA"})
        # We do it this way because without a canonical way to generate JSON we can't risk reordering breaking the CRC.
        return temp.replace('"DATA"', blob.decode('utf-8'))

    def _mqtt_send(self, payload):
        url = DEFAULT_URL_BASE + "hes-gateway/terminal/sendMqtt"

        res = self._post(url, payload)
        if res['code'] == 102:
            raise DeviceTimeoutException(res['message'])
        assert res['code'] == 200, f"{res['code']}: {res['message']}"
        return res


class UnknownMethodsClient(Client):
    """A client that also implements some methods that don't obviously work, for research purposes"""

    def get_controllable_loads(self):
        url = self.url_base + "hes-gateway/terminal/selectTerGatewayControlLoadByGatewayId"
        params = { "id": self.gateway, "lang": "en_US" }
        headers = { "loginToken": self.token }
        res = requests.get(url, params=params, headers=headers)
        return res.json()

    def get_accessory_list(self):
        url = self.url_base + "hes-gateway/terminal/getIotAccessoryList"
        params = { "gatewayId": self.gateway, "lang": "en_US" }
        headers = { "loginToken": self.token }
        res = requests.get(url, params=params, headers=headers)
        return res.json()

    def get_equipment_list(self):
        url = self.url_base + "hes-gateway/manage/getEquipmentList"
        params = { "gatewayId": self.gateway, "lang": "en_US" }
        headers = { "loginToken": self.token }
        res = requests.get(url, params=params, headers=headers)
        return res.json()
