"""Client for interacting with FranklinWH gateway API.

This module provides classes and functions to authenticate, send commands,
and retrieve statistics from FranklinWH energy gateway devices.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import functools
import hashlib
import json
import logging
import time
from typing import Any, Final
import zlib

import httpx

from .api import DEFAULT_URL_BASE, ISSUES_URL


def time_cached(ttl: timedelta = timedelta(seconds=2)):
    """Decorator to cache function results for a specified time-to-live (TTL)."""

    def wrapper(func):
        cache = {}

        @functools.wraps(func)
        async def wrapped(*args, **kwargs):
            now = datetime.now()
            key = (func.__name__, args, frozenset(kwargs.items()))
            if key in cache:
                lock = cache[key][2]
            else:
                lock = asyncio.Lock()
                cache[key] = (now - ttl, None, lock)
            async with lock:
                if now < cache[key][0]:
                    return cache[key][1]
                result = await func(*args, **kwargs)
                cache[key] = (now + ttl, result, lock)
            return result

        wrapped.clear = cache.clear
        return wrapped

    return wrapper


class SwitchState(tuple[bool | None, bool | None, bool | None]):
    """Represents the state of the smart switches connected to the FranklinWH gateway.

    Each element in the tuple corresponds to a switch:
        - True: Switch is ON
        - False: Switch is OFF
        - None: Switch state is unchanged
    """

    __slots__ = ()

    def __new__(cls, lst: list[bool | None]):
        """Convert a list to a SwitchState tuple.

        Parameters
        ----------
        lst : list[bool | None]
            The list to convert.

        Returns:
        -------
        SwitchState
            The converted SwitchState tuple.
        """
        if len(lst) != 3:
            raise ValueError(
                "List must have exactly 3 elements to convert to SwitchState."
            )
        return super().__new__(cls, (lst[0], lst[1], lst[2]))


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
            False,
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

    @staticmethod
    def from_offgridreason(value: int | None) -> GridStatus:
        """Convert an offgridreason value to a GridStatus.

        Parameters
        ----------
        value : int | None
            The offgridreason value to convert.

        Returns:
        -------
        GridStatus
            The corresponding GridStatus.
        """
        match value:
            case None | -1:
                return GridStatus.NORMAL
            case 0:
                return GridStatus.DOWN
            case 1:
                return GridStatus.OFF
            case _:
                raise ValueError(f"Unknown offgridreason value: {value}")


@dataclass
class Current:
    """Current statistics for FranklinWH gateway."""

    solar_production: float
    generator_production: float
    generator_enabled: bool
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


class WorkMode(Enum):
    """Represents the workMode values of the FranklinWH gateway.

    These are the only operating mode constants in the FranklinWH API.

    Attributes:
        TIME_OF_USE (int): Time of Use mode.
        SELF_CONSUMPTION (int): Self Consumption mode.
        EMERGENCY_BACKUP (int): Emergency Backup mode.

    These modes are artificial and describe extended behaviors.

    Attributes:
        VPP_MODE (int): Virtual Power Plant mode, controlled by provider.
    """

    TIME_OF_USE = 1
    SELF_CONSUMPTION = 2
    EMERGENCY_BACKUP = 3
    VPP_MODE = 9


class Mode:
    """Represents an operating mode for the FranklinWH gateway.

    Provides static methods to create specific modes (time of use, emergency backup, self consumption)
    and generates payloads for API requests to set the gateway's operating mode.

    Methods:
    -------
    time_of_use(optional soc)
        Create a time of use mode instance.
    emergency_backup(optional soc)
        Create an emergency backup mode instance.
    self_consumption(optional soc)
        Create a self consumption mode instance.
    payload(gateway)
        Generate the payload dictionary for API requests.
    """

    TIME_OF_USE_NAME: Final = "Time Of Use (TOU)"
    SELF_CONSUMPTION_NAME: Final = "Self-Consumption"
    EMERGENCY_BACKUP_NAME: Final = "Emergency Backup"
    VPP_MODE_NAME: Final = "VPP Mode"

    NAMES: Final = {
        WorkMode.TIME_OF_USE.value: TIME_OF_USE_NAME,
        WorkMode.SELF_CONSUMPTION.value: SELF_CONSUMPTION_NAME,
        WorkMode.EMERGENCY_BACKUP.value: EMERGENCY_BACKUP_NAME,
        WorkMode.VPP_MODE.value: VPP_MODE_NAME,
    }
    assert len(NAMES) == len(WorkMode), "All WorkModes must have names defined."

    _modes: dict[int, Any] = {
        WorkMode.VPP_MODE.value: {  # compatible with result of getGatewayTouListV2
            "id": WorkMode.VPP_MODE.value,
            "oldIndex": 3,
            "name": VPP_MODE_NAME,
            "soc": 100.0,
            "maxSoc": 100.0,
            "minSoc": 100.0,
            "dischargeDepthSoc": None,
            "editSocFlag": False,
            "multiSOCFlag": False,
            "workMode": WorkMode.VPP_MODE.value,
            "energyIncentivesType": 0,
            "electricityType": 1,
            "displayFlag": None,
        }
    }

    @classmethod
    @time_cached(timedelta(hours=1))  # eventually consistent with changes via app
    async def get_modes(cls, client: Client) -> dict[int, Any]:
        """Get the available modes for the FranklinWH gateway.

        MUST be called once before using other methods, e.g., through get_mode().

        Parameters
        ----------
        client : Client
            The FranklinWH client instance.

        Returns:
        -------
        dict[int, Any]
            A dictionary of available modes keyed by workMode.

        get_modes[TIME_OF_USE]["name"] returns the actual rate name
        """
        body = await client._post(  # noqa: SLF001
            DEFAULT_URL_BASE + "hes-gateway/terminal/tou/getGatewayTouListV2", None
        )
        for v in body["result"]["list"]:
            cls._modes[v["workMode"]] = v
        return cls._modes

    @classmethod
    def time_of_use(cls, soc: int | None = None) -> Mode:
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
        if soc is None:
            soc = 20
        return Mode(WorkMode.TIME_OF_USE.value, soc)

    @classmethod
    def emergency_backup(cls, soc: int | None = None) -> Mode:
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
        if soc is None:
            soc = 100
        return Mode(WorkMode.EMERGENCY_BACKUP.value, soc)

    @classmethod
    def self_consumption(cls, soc: int | None = None) -> Mode:
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
        if soc is None:
            soc = 20
        return Mode(WorkMode.SELF_CONSUMPTION.value, soc)

    @classmethod
    def vpp_mode(cls, _: int | None = None) -> Mode:
        """Create a virtual power plant mode instance.

        Returns:
        -------
        Mode
            An instance of Mode configured for virtual power plant mode.
        """
        return Mode(WorkMode.VPP_MODE.value, 100)

    @classmethod
    def get_by_name(cls, name: str) -> Mode:
        """Get a Mode instance by its name.

        Parameters
        ----------
        name : str
            The name of the mode.

        Returns:
        -------
        Mode
            An instance of Mode corresponding to the given name.

        Raises:
        ------
        ValueError
            If the mode name is unknown.
        """
        for workMode, mode_name in cls.NAMES.items():
            if mode_name == name:
                return Mode(workMode, cls._modes[workMode].get("soc"))
        raise ValueError(f"Unknown mode name: {name}")

    def __init__(self, workMode: int, soc: int) -> None:
        """Initialize a Mode instance with the given state of charge.

        Parameters
        ----------
        soc : int
            The state of charge value for the mode.
        """
        self.workMode = workMode
        self.soc = soc
        mode = self._modes[workMode]
        self.name = self.NAMES[workMode]
        self.currendId = mode["id"]
        self.oldIndex = mode["oldIndex"]

    def payload(self, gateway, soc: int | None = None) -> dict:
        """Generate the payload dictionary for API requests to set the gateway's operating mode.

        Parameters
        ----------
        gateway : str
            The gateway identifier.
        soc : int, optional
            New State of Charge value.

        Returns:
        -------
        dict
            The payload dictionary for the API request.
        """
        params = {
            "currendId": str(self.currendId),
            "gatewayId": gateway,
            "lang": "EN_US",
            "oldIndex": str(self.oldIndex),
            "stromEn": "1",
            "workMode": str(self.workMode),
        }
        if soc is not None:
            params["soc"] = str(soc)
        return params


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

    def __init__(self, username: str, password: str, **kwargs) -> None:
        """Initialize the TokenFetcher with the provided username and password."""
        self.username = username
        self.password = password
        self.session = kwargs.get("session")
        self.info: dict | None = None

    async def get_token(self):
        """Fetch a new authentication token using the stored credentials.

        Store the intermediate account information in self.info.
        """
        self.info = await TokenFetcher._login(
            self.username, self.password, self.session or httpx.AsyncClient(http2=True)
        )
        return self.info["token"]

    @staticmethod
    async def login(username: str, password: str):
        """Log in to the FranklinWH API and retrieve an authentication token."""
        return (
            await TokenFetcher._login(username, password, httpx.AsyncClient(http2=True))
        )["token"]

    @staticmethod
    async def _login(username: str, password: str, session: httpx.AsyncClient) -> dict:
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
        res = await session.post(url, data=form, timeout=10)
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
        self,
        fetcher: TokenFetcher,
        gateway: str,
        url_base: str = DEFAULT_URL_BASE,
        **kwargs,
    ) -> None:
        """Initialize the Client with the provided TokenFetcher, gateway ID, and optional URL base."""
        self.fetcher = fetcher
        self.gateway = gateway
        self.url_base = url_base
        self.token = ""
        self.snno = 0
        # avoid even creating a new AsyncClient unless required
        self.session = (
            httpx.AsyncClient(http2=True)
            if "session" not in kwargs
            else kwargs["session"]
        )

        # to enable detailed logging add this to configuration.yaml:
        # logger:
        #   logs:
        #     franklinwh: debug

        self.logger = logging.getLogger("franklinwh")
        if self.logger.isEnabledFor(logging.DEBUG):

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

            self.session.event_hooks["request"].append(debug_request)
            self.session.event_hooks["response"].append(debug_response)

    # TODO(richo) Setup timeouts and deal with them gracefully.
    async def _post(self, url, payload, params: dict | None = None):
        if params is None:
            params = {}
        else:
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

    async def get_smart_switch_state(self) -> SwitchState:
        """Get the current state of the smart switches."""
        # TODO(richo) This API is super in flux, both because of how vague the
        # underlying API is and also trying to figure out what to do with
        # inconsistency.
        # Whether this should use the _switch_status() API is super unclear.
        # Maybe I will reach out to FranklinWH once I have published.
        status = await self._status()
        switches = [x == 1 for x in status["pro_load"]]
        return SwitchState(switches)

    async def set_smart_switch_state(self, state: SwitchState):
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
    @time_cached()
    async def _status(self):
        payload = self._build_payload(203, {"opt": 1, "refreshData": 1})
        data = (await self._mqtt_send(payload))["result"]["dataArea"]
        return json.loads(data)

    # Sends a 311 which appears to be a more specific switch command
    @time_cached()
    async def _switch_status(self):
        payload = self._build_payload(311, {"opt": 0, "order": self.gateway})
        data = (await self._mqtt_send(payload))["result"]["dataArea"]
        return json.loads(data)

    # Sends a 353 which grabs real-time smart-circuit load information
    # https://github.com/richo/homeassistant-franklinwh/issues/27#issuecomment-2714422732
    @time_cached()
    async def _switch_usage(self):
        payload = self._build_payload(353, {"opt": 0, "order": self.gateway})
        data = (await self._mqtt_send(payload))["result"]["dataArea"]
        return json.loads(data)

    async def set_mode(self, mode: Mode):
        """Set the operating mode of the FranklinWH gateway."""
        if mode.workMode == WorkMode.VPP_MODE.value:
            raise ValueError(
                Mode.VPP_MODE_NAME
                + " cannot be set directly, it is controlled by the provider."
            )
        url = self.url_base + "hes-gateway/terminal/tou/updateTouModeV2"
        payload = mode.payload(self.gateway)
        await self._post_form(url, payload)
        Mode.get_modes.clear()

    async def get_mode(self) -> Mode:
        """Get the current operating mode of the FranklinWH gateway."""
        modes = await Mode.get_modes(self)
        status = await self.get_composite_info()
        for v in modes.values():
            if v["id"] == status["runtimeData"]["mode"]:
                return Mode(v["workMode"], v.get("soc"))
        self.logger.warning(
            "Unknown mode ID: %s, please report at %s",
            status["runtimeData"]["mode"],
            ISSUES_URL,
        )
        return modes[status["currentWorkMode"]]

    async def set_backup_reserve(self, soc: int) -> None:
        """Set the backup reserve for the FranklinWH gateway.

        Parameters
        ----------
        soc : int
            The desired State of Charge percentage to set for backup reserve.
        """
        mode = await self.get_mode()
        if mode.workMode == WorkMode.VPP_MODE.value:
            raise ValueError(
                "Backup Reserve cannot be set in "
                + Mode.VPP_MODE_NAME
                + ", it is controlled by the provider."
            )
        url = self.url_base + "hes-gateway/terminal/tou/updateSocV2"
        params = {
            "soc": soc,
            "workMode": mode.workMode,
        }
        await self._post(url, None, params)
        Mode.get_modes.clear()

    async def get_stats(self) -> Stats:
        """Get current statistics for the FHP.

        This includes instantaneous measurements for current power, as well as totals for today (in local time)
        """
        tasks = [f() for f in [self.get_composite_info, self._switch_usage]]
        results = await asyncio.gather(*tasks)
        data = results[0]["runtimeData"]
        grid_status: GridStatus = GridStatus.NORMAL
        if "offgridreason" in data:
            grid_status = GridStatus.from_offgridreason(data["offgridreason"])
        sw_data = results[1]

        return Stats(
            Current(
                data["p_sun"],
                data["p_gen"],
                data["genStat"] > 1,
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
        raw = json.dumps(data, separators=(",", ":"))
        blob = raw.encode("utf-8")
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
        return temp.replace('"DATA"', raw)

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

    @time_cached()
    async def get_composite_info(self):
        """Get composite information about the FranklinWH gateway."""
        url = self.url_base + "hes-gateway/terminal/getDeviceCompositeInfo"
        params = {"refreshFlag": 1}
        return (await self._get(url, params))["result"]

    async def set_generator(self, enabled: bool):
        """Enable or disable the generator on the FranklinWH gateway.

        Parameters
        ----------
        enabled : bool
            True to enable the generator, False to disable it.
        """
        url = self.url_base + "hes-gateway/terminal/updateIotGenerator"
        payload = {"manuSw": 1 + int(enabled), "gatewayId": self.gateway, "opt": 1}
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
