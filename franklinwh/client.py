import requests
import urllib3
from dataclasses import dataclass

DEFAULT_URL_BASE = "https://energy.franklinwh.com";

@dataclass
class Stats:
    # Instant measurements
    solar_yield: float


    # Current battery %
    battery_soc: float

    # Today's totals






class Client(object):
    def __init__(self, token: str, gateway: str, url_base: str = DEFAULT_URL_BASE):
        self.token = token
        self.gateway = gateway
        self.url_base = url_base

    def get_stats(self):
        url = urllib3.util.parse_url(self.url_base)
        url.path = "hes-gateway/terminal/selectIotUserRuntimeDataLog"
        params = { "gatewayId": self.gateway, "lang": "en_US" }
        headers = { "loginToken": self.token }
        res = requests.get(url.url, params=params, headers=headers)
        json = res.json()


