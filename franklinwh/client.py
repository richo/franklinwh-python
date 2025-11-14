"""Client for interacting with FranklinWH gateway API.

This module provides classes and functions to authenticate, send commands,
and retrieve statistics from FranklinWH energy gateway devices.
"""

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import logging
import time
import zlib

import httpx

from .api import DEFAULT_URL_BASE


class AccessoryType(Enum):
    """Represents the type of accessory connected to the FranklinWH gateway.

    Attributes:
        SMART_CIRCUIT_MODULE (int): A Smart Circuit module, see https://www.franklinwh.com/document/download/smart-circuits-module-installation-guide-sku-accy-scv2-us
        GENERATOR_MODULE (int): A Generator module, see https://www.franklinwh.com/document/download/generator-module-installation-guide-sku-accy-genv2-us
    """

    GENERATOR_MODULE = 3
    SMART_CIRCUIT_MODULE = 4


def to_hex(inp):
    """Convert an integer to an 8-character uppercase hexadecimal string.

    Parameters
    ----------
    inp : int
        The integer to convert.

    Returns:
    -------
    str
        The hexadecimal string representation of the input.
    """
    return f"{inp:08X}"


def empty_stats():
    """Return a Stats object with all values set to zero.

    Returns:
    -------
    Stats
        A Stats object with zeroed Current and Totals values.
    """
    return Stats(
        Current(
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            GridStatus.NORMAL,
        ),
        Totals(
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
        ),
    )


class GridStatus(Enum):
    """Represents the status of the grid connection for the FranklinWH gateway.

    Attributes:
        NORMAL (int): Grid connection is normal / up.
        DOWN (int): Grid connection is abnormal / down.
        OFF (int): Grid connection is turned off at the gateway.

    OFF is set by software, specifically Settings / Go Off-Grid in the app.
    DOWN is external to the gateway.
    NORMAL indicates normal operation.
    """

    NORMAL = 0
    DOWN = 1
    OFF = 2


@dataclass
class Current:
    """Current statistics for FranklinWH gateway."""

    solar_production: float
    generator_production: float
    battery_use: float
    grid_use: float
    home_load: float
    battery_soc: float
    switch_1_load: float
    switch_2_load: float
    v2l_use: float
    grid_status: GridStatus


@dataclass
class Totals:
    """Total energy statistics for FranklinWH gateway."""

    battery_charge: float
    battery_discharge: float
    grid_import: float
    grid_export: float
    solar: float
    generator: float
    home_use: float
    switch_1_use: float
    switch_2_use: float
    v2l_export: float
    v2l_import: float


@dataclass
class Stats:
    """Statistics for FranklinWH gateway."""

    current: Current
    totals: Totals


MODE_TIME_OF_USE = "time_of_use"
MODE_SELF_CONSUMPTION = "self_consumption"
MODE_EMERGENCY_BACKUP = "emergency_backup"

MODE_MAP = {
    9322: MODE_TIME_OF_USE,
    9323: MODE_SELF_CONSUMPTION,
    9324: MODE_EMERGENCY_BACKUP,
}


class Mode:
    """Represents an operating mode for the FranklinWH gateway.

    Provides static methods to create specific modes (time of use, emergency backup, self consumption)
    and generates payloads for API requests to set the gateway's operating mode.

    Attributes:
    ----------
    soc : int
        The state of charge value for the mode.
    currendId : int | None
        The current mode identifier.
    workMode : int | None
        The work mode value.

    Methods:
    -------
    time_of_use(soc=20)
        Create a time of use mode instance.
    emergency_backup(soc=100)
        Create an emergency backup mode instance.
    self_consumption(soc=20)
        Create a self consumption mode instance.
    payload(gateway)
        Generate the payload dictionary for API requests.
    """

    @staticmethod
    def time_of_use(soc=20):
        """Create a time of use mode instance.

        Parameters
        ----------
        soc : int, optional
            The state of charge value for the mode, defaults to 20.

        Returns:
        -------
        Mode
            An instance of Mode configured for time of use.
        """
        mode = Mode(soc)
        mode.currendId = 9322
        mode.workMode = 1
        return mode

    @staticmethod
    def emergency_backup(soc=100):
        """Create an emergency backup mode instance.

        Parameters
        ----------
        soc : int, optional
            The state of charge value for the mode, defaults to 100.

        Returns:
        -------
        Mode
            An instance of Mode configured for emergency backup.
        """
        mode = Mode(soc)
        mode.currendId = 9324
        mode.workMode = 3
        return mode

    @staticmethod
    def self_consumption(soc=20):
        """Create a self consumption mode instance.

        Parameters
        ----------
        soc : int, optional
            The state of charge value for the mode, defaults to 20.

        Returns:
        -------
        Mode
            An instance of Mode configured for self consumption.
        """
        mode = Mode(soc)
        mode.currendId = 9323
        mode.workMode = 2
        return mode

    def __init__(self, soc: int) -> None:
        """Initialize a Mode instance with the given state of charge.

        Parameters
        ----------
        soc : int
            The state of charge value for the mode.
        """
        self.soc = soc
        self.currendId = None
        self.workMode = None

    def payload(self, gateway) -> dict:
        """Generate the payload dictionary for API requests to set the gateway's operating mode.

        Parameters
        ----------
        gateway : str
            The gateway identifier.

        Returns:
        -------
        dict
            The payload dictionary for the API request.
        """
        return {
            "currendId": str(self.currendId),
            "gatewayId": gateway,
            "lang": "EN_US",
            "oldIndex": "1",  # Who knows if this matters
            "soc": str(self.soc),
            "stromEn": "1",
            "workMode": str(self.workMode),
        }


class TokenExpiredException(Exception):
    """raised when the token has expired to signal upstream that you need to create a new client or inject a new token."""


class AccountLockedException(Exception):
    """raised when the account is locked."""


class InvalidCredentialsException(Exception):
    """raised when the credentials are invalid."""


class DeviceTimeoutException(Exception):
    """raised when the device times out."""


class GatewayOfflineException(Exception):
    """raised when the gateway is offline."""


class TokenFetcher:
    """Fetches and refreshes authentication tokens for FranklinWH API."""

    def __init__(self, username: str, password: str) -> None:
        """Initialize the TokenFetcher with the provided username and password."""
        self.username = username
        self.password = password
        self.info: dict | None = None

    async def get_token(self):
        """Fetch a new authentication token using the stored credentials.

        Store the intermediate account information in self.info.
        """
        self.info = await TokenFetcher._login(self.username, self.password)
        return self.info["token"]

    @staticmethod
    async def login(username: str, password: str):
        """Log in to the FranklinWH API and retrieve an authentication token."""
        return (await TokenFetcher._login(username, password))["token"]

    @staticmethod
    async def _login(username: str, password: str) -> dict:
        """Log in to the FranklinWH API and retrieve account information."""
        url = (
            DEFAULT_URL_BASE + "hes-gateway/terminal/initialize/appUserOrInstallerLogin"
        )
        form = {
            "account": username,
            "password": hashlib.md5(bytes(password, "ascii")).hexdigest(),
            "lang": "en_US",
            "type": 1,
        }
        async with httpx.AsyncClient(http2=True) as client:
            res = await client.post(url, data=form, timeout=10)
        res.raise_for_status()
        js = res.json()

        if js["code"] == 401:
            raise InvalidCredentialsException(js["message"])

        if js["code"] == 400:
            raise AccountLockedException(js["message"])

        return js["result"]


async def retry(func, filter, refresh_func):
    """Tries calling func, and if filter fails it calls refresh func then tries again."""
    res = await func()
    if filter(res):
        return res
    await refresh_func()
    return await func()


class Client:
    """Client for interacting with FranklinWH gateway API."""

    def __init__(
        self, fetcher: TokenFetcher, gateway: str, url_base: str = DEFAULT_URL_BASE
    ) -> None:
        """Initialize the Client with the provided TokenFetcher, gateway ID, and optional URL base."""
        self.fetcher = fetcher
        self.gateway = gateway
        self.url_base = url_base
        self.token = ""
        self.snno = 0
        self.session = httpx.AsyncClient(http2=True)

        # to enable detailed logging add this to configuration.yaml:
        # logger:
        #   logs:
        #     franklinwh: debug

        logger = logging.getLogger("franklinwh")
        if logger.isEnabledFor(logging.DEBUG):

            async def debug_request(request: httpx.Request):
                body = request.content
                if body and request.headers.get("Content-Type", "").startswith(
                    "application/json"
                ):
                    body = json.dumps(json.loads(body), ensure_ascii=False)
                self.logger.debug(
                    "Request: %s %s %s %s",
                    request.method,
                    request.url,
                    request.headers,
                    body,
                )
                return request

            async def debug_response(response: httpx.Response):
                await response.aread()
                self.logger.debug(
                    "Response: %s %s %s %s",
                    response.status_code,
                    response.url,
                    response.headers,
                    response.json(),
                )
                return response

            self.logger = logger
            self.session = httpx.AsyncClient(
                http2=True,
                event_hooks={
                    "request": [debug_request],
                    "response": [debug_response],
                },
            )

    # TODO(richo) Setup timeouts and deal with them gracefully.
    async def _post(self, url, payload, params: dict | None = None):
        if params is not None:
            params = params.copy()
            params.update({"gatewayId": self.gateway, "lang": "en_US"})

        async def __post():
            return (
                await self.session.post(
                    url,
                    params=params,
                    headers={
                        "loginToken": self.token,
                        "Content-Type": "application/json",
                    },
                    data=payload,
                )
            ).json()

        return await retry(__post, lambda j: j["code"] != 401, self.refresh_token)

    async def _post_form(self, url, payload):
        async def __post():
            return (
                await self.session.post(
                    url,
                    headers={
                        "loginToken": self.token,
                        "Content-Type": "application/x-www-form-urlencoded",
                        "optsource": "3",
                    },
                    data=payload,
                )
            ).json()

        return await retry(__post, lambda j: j["code"] != 401, self.refresh_token)

    async def _get(self, url, params: dict | None = None):
        if params is None:
            params = {}
        else:
            params = params.copy()
        params.update({"gatewayId": self.gateway, "lang": "en_US"})

        async def __get():
            return (
                await self.session.get(
                    url, params=params, headers={"loginToken": self.token}
                )
            ).json()

        return await retry(__get, lambda j: j["code"] != 401, self.refresh_token)

    async def refresh_token(self):
        """Refresh the authentication token using the TokenFetcher."""
        self.token = await self.fetcher.get_token()

    async def get_accessories(self):
        """Get the list of accessories connected to the gateway."""
        url = self.url_base + "hes-gateway/common/getAccessoryList"
        # with no accessories this returns:
        # {"code":200,"message":"Query success!","result":[],"success":true,"total":0}
        return (await self._get(url))["result"]

    async def get_smart_switch_state(self):
        """Get the current state of the smart switches."""
        # TODO(richo) This API is super in flux, both because of how vague the
        # underlying API is and also trying to figure out what to do with
        # inconsistency.
        # Whether this should use the _switch_status() API is super unclear.
        # Maybe I will reach out to FranklinWH once I have published.
        status = await self._status()
        switches = (x == 1 for x in status["pro_load"])
        return tuple(switches)

    async def set_smart_switch_state(
        self, state: tuple[bool | None, bool | None, bool | None]
    ):
        """Set the state of the smart circuits.

        Setting a value in the state tuple to True will turn on that circuit,
        setting to False will turn it off. Setting to None will make it
        unchanged.
        """

        payload = await self._switch_status()
        payload["opt"] = 1
        payload.pop("modeChoose")
        payload.pop("result")

        if payload["SwMerge"] == 1:
            if state[0] != state[1]:
                raise RuntimeError(
                    "Smart switches 1 and 2 are merged! Setting them to different values could do bad things to your house. Aborting."
                )

        def set_value(keys, value):
            for k in keys:
                payload[k] = value

        for i in range(3):
            sw = i + 1
            if state[i] is not None:
                mode = f"Sw{sw}Mode"
                msg_type = f"Sw{sw}MsgType"
                pro_load = f"Sw{sw}ProLoad"

                payload[msg_type] = 1
                payload[mode] = int(bool(state[i]))
                payload[pro_load] = payload[mode] ^ 1

        wire_payload = self._build_payload(311, payload)
        data = (await self._mqtt_send(wire_payload))["result"]["dataArea"]
        return json.loads(data)

    # Sends a 203 which is a high level status
    async def _status(self):
        payload = self._build_payload(203, {"opt": 1, "refreshData": 1})
        data = (await self._mqtt_send(payload))["result"]["dataArea"]
        return json.loads(data)

    # Sends a 311 which appears to be a more specific switch command
    async def _switch_status(self):
        payload = self._build_payload(311, {"opt": 0, "order": self.gateway})
        data = (await self._mqtt_send(payload))["result"]["dataArea"]
        return json.loads(data)

    # Sends a 353 which grabs real-time smart-circuit load information
    # https://github.com/richo/homeassistant-franklinwh/issues/27#issuecomment-2714422732
    async def _switch_usage(self):
        payload = self._build_payload(353, {"opt": 0, "order": self.gateway})
        data = (await self._mqtt_send(payload))["result"]["dataArea"]
        return json.loads(data)

    async def set_mode(self, mode):
        """Set the operating mode of the FranklinWH gateway."""
        # Time of use:
        # currendId=9322&gatewayId=___&lang=EN_US&oldIndex=3&soc=15&stromEn=1&workMode=1

        # Emergency Backup:
        # currendId=9324&gatewayId=___&lang=EN_US&oldIndex=1&soc=100&stromEn=1&workMode=3

        # Self consumption
        # currendId=9323&gatewayId=___&lang=EN_US&oldIndex=2&soc=20&stromEn=1&workMode=2
        url = DEFAULT_URL_BASE + "hes-gateway/terminal/tou/updateTouMode"
        payload = mode.payload(self.gateway)
        await self._post_form(url, payload)

    async def get_mode(self):
        """Get the current operating mode of the FranklinWH gateway."""
        status = await self._switch_status()
        # TODO(richo) These are actually wrong but I can't obviously find where to get the correct values right now.
        mode_name = MODE_MAP[status["runingMode"]]
        if mode_name == MODE_TIME_OF_USE:
            return (mode_name, status["touMinSoc"])
        if mode_name == MODE_SELF_CONSUMPTION:
            return (mode_name, status["selfMinSoc"])
        if mode_name == MODE_EMERGENCY_BACKUP:
            return (mode_name, status["backupMaxSoc"])
        raise RuntimeError(f"Unknown mode {status['runingMode']}")

    async def get_stats(self) -> Stats:
        """Get current statistics for the FHP.

        This includes instantaneous measurements for current power, as well as totals for today (in local time)
        """
        data = await self._status()
        grid_status: GridStatus = GridStatus.NORMAL
        if "offgridreason" in data:
            grid_status = GridStatus(1 + data["offgridreason"])
        sw_data = await self._switch_usage()

        return Stats(
            Current(
                data["p_sun"],
                data["p_gen"],
                data["p_fhp"],
                data["p_uti"],
                data["p_load"],
                data["soc"],
                sw_data["SW1ExpPower"],
                sw_data["SW2ExpPower"],
                sw_data["CarSWPower"],
                grid_status,
            ),
            Totals(
                data["kwh_fhp_chg"],
                data["kwh_fhp_di"],
                data["kwh_uti_in"],
                data["kwh_uti_out"],
                data["kwh_sun"],
                data["kwh_gen"],
                data["kwh_load"],
                sw_data["SW1ExpEnergy"],
                sw_data["SW2ExpEnergy"],
                sw_data["CarSWExpEnergy"],
                sw_data["CarSWImpEnergy"],
            ),
        )

    def next_snno(self):
        """Get the next sequence number for API requests."""
        self.snno += 1
        return self.snno

    def _build_payload(self, ty, data):
        blob = json.dumps(data, separators=(",", ":")).encode("utf-8")
        # crc = to_hex(zlib.crc32(blob.encode("ascii")))
        crc = to_hex(zlib.crc32(blob))
        ts = int(time.time())

        temp = json.dumps(
            {
                "lang": "EN_US",
                "cmdType": ty,
                "equipNo": self.gateway,
                "type": 0,
                "timeStamp": ts,
                "snno": self.next_snno(),
                "len": len(blob),
                "crc": crc,
                "dataArea": "DATA",
            }
        )
        # We do it this way because without a canonical way to generate JSON we can't risk reordering breaking the CRC.
        return temp.replace('"DATA"', blob.decode("utf-8"))

    async def _mqtt_send(self, payload):
        url = DEFAULT_URL_BASE + "hes-gateway/terminal/sendMqtt"

        res = await self._post(url, payload)
        if res["code"] == 102:
            raise DeviceTimeoutException(res["message"])
        if res["code"] == 136:
            raise GatewayOfflineException(res["message"])
        assert res["code"] == 200, f"{res['code']}: {res['message']}"
        return res

    async def set_grid_status(self, status: GridStatus, soc: int = 5):
        """Set the grid status of the FranklinWH gateway.

        Parameters
        ----------
        status : GridStatus
            The desired grid status to set.
        """
        url = self.url_base + "hes-gateway/terminal/updateOffgrid"
        payload = {
            "gatewayId": self.gateway,
            "offgridSet": int(status != GridStatus.NORMAL),
            "offgridSoc": soc,
        }
        await self._post(url, json.dumps(payload))


class UnknownMethodsClient(Client):
    """A client that also implements some methods that don't obviously work, for research purposes."""

    async def get_controllable_loads(self):
        """Get the list of controllable loads connected to the gateway."""
        url = (
            self.url_base
            + "hes-gateway/terminal/selectTerGatewayControlLoadByGatewayId"
        )
        params = {"id": self.gateway, "lang": "en_US"}
        headers = {"loginToken": self.token}
        res = await self.session.get(url, params=params, headers=headers)
        return res.json()

    async def get_accessory_list(self):
        """Get the list of accessories connected to the gateway."""
        url = self.url_base + "hes-gateway/terminal/getIotAccessoryList"
        params = {"gatewayId": self.gateway, "lang": "en_US"}
        headers = {"loginToken": self.token}
        res = await self.session.get(url, params=params, headers=headers)
        return res.json()

    async def get_equipment_list(self):
        """Get the list of equipment connected to the gateway."""
        url = self.url_base + "hes-gateway/manage/getEquipmentList"
        params = {"gatewayId": self.gateway, "lang": "en_US"}
        headers = {"loginToken": self.token}
        res = await self.session.get(url, params=params, headers=headers)
        return res.json()
