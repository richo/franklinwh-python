import requests
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

    def get_stats(self) -> dict:
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





