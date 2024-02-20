import requests
import hashlib
from dataclasses import dataclass

DEFAULT_URL_BASE = "https://energy.franklinwh.com/";

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


class Client(object):
    def __init__(self, token: str, gateway: str, url_base: str = DEFAULT_URL_BASE):
        self.token = "APP_ACCOUNT:" + token
        self.gateway = gateway
        self.url_base = url_base

    def login(self, username: str, password: str):
        url = self.url_base + "hes-gateway/manage/appUserOrInstallerLogin"
        hash = hashlib.md5(bytes(password, "ascii")).hexdigest()
        form = {
                "account": username,
                "password": hash,
                "lang": "en_US",
                "type": 1,
                }
        res = requests.get(url, data=form)
        return res.json()

    def _get_smart_switch_state(self):
        url = self.url_base + "hes-gateway/manage/getCommunicationOptimization"
        params = { "gatewayId": self.gateway, "lang": "en_US" }
        headers = { "loginToken": self.token }
        res = requests.get(url, params=params, headers=headers)
        return res.json()

    def get_smart_switch_state(self):
        # TODO(richo) This API is super in flux, both because of how vague the
        # underlying API is and also trying to figure out what to do with
        # inconsistency.
        data = self._get_smart_switch_state()
        def state(swmode, swproload):
            if swmode == 1 and swproload == 1:
                return True
            elif swmode == 0 and swproload == 0:
                return False
            print("Not sure we understand this state: {}, {}".format(swmode, swproload))
            return None

        result = data["result"]
        sw1 = state(result["Sw1Mode"], result["Sw1ProLoad"])
        sw2 = state(result["Sw2Mode"], result["Sw2ProLoad"])
        sw3 = state(result["Sw3Mode"], result["Sw3ProLoad"])

        return [sw1, sw2, sw3]



    def set_smart_switch_state(self):

        pass
        # TODO(richo)
        # Set all of these to 1.
        # Sw1Mode
        # Sw2Mode
        # Sw1ProLoad
        # Sw2ProLoad

    def get_stats(self) -> dict:
        """Get current statistics for the FHP.

        This includes instantaneous measurements for current power, as well as totals for today (in local time)
        """
        url = self.url_base + "hes-gateway/terminal/selectIotUserRuntimeDataLog"
        params = { "gatewayId": self.gateway, "lang": "en_US" }
        headers = { "loginToken": self.token }
        res = requests.get(url, params=params, headers=headers)
        json = res.json()
        data = json["result"]["dataArea"]

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
