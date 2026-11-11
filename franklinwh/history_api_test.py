"""Tests for the historical endpoints: get_power_by_day / get_electric_daily.

Fixtures are live captures; see history_test.py. The parsing logic is pure
given a result dict, so most tests drive it through a stub client whose
_get() returns the fixture -- no network, no token.
"""

import asyncio

import pytest

from .client import Client, PowerByDay, PowerSample
from .history_test import ELECTRIC_DAILY, POWER_BY_DAY


def _power_by_day(client):
    return asyncio.run(Client.get_power_by_day(client, "2026-11-03"))


def _electric_daily(client):
    return asyncio.run(Client.get_electric_daily(client, "2026-11-03"))


class _StubClient:
    """A Client double: routes _get() to canned results by path fragment."""

    url_base = "https://energy.franklinwh.com/"

    def __init__(self, results):
        self._results = results
        self.calls = []

    async def _get(self, url, params=None):
        self.calls.append((url, params))
        for fragment, res in self._results.items():
            if fragment in url:
                return {"code": 200, "result": res, "success": True}
        raise AssertionError(f"unexpected url {url}")


def _power_client():
    return _StubClient({"getFhpPowerByDay": POWER_BY_DAY["result"]})


def _electric_client():
    return _StubClient({"getFhpElectricData": ELECTRIC_DAILY["result"]})


# ---- get_power_by_day -----------------------------------------------------------

def test_power_by_day_parses_all_samples():
    client = _power_client()
    pb = _power_by_day(client)
    assert isinstance(pb, PowerByDay)
    assert pb.day == "2026-11-03"
    assert [s.ts for s in pb.samples] == POWER_BY_DAY["result"]["deviceTimeArray"]


def test_power_by_day_derives_aggregates():
    client = _power_client()
    pb = _power_by_day(client)
    # noon row: solar 1.812+1.144+0.013, home = solarHome+gridHome+fhpHome+genHome+v2lHome
    s = pb.samples[4]
    assert s.solar == pytest.approx(1.812 + 1.144 + 0.013)
    assert s.home == pytest.approx(1.812)  # gridHome=fhpHome=genHome=v2lHome=0 at 09:00
    assert s.grid_import == 0.0
    assert s.grid_export == pytest.approx(1.144)
    assert s.battery_soc == pytest.approx(99.8)


def test_power_by_day_zero_hour_row_is_grid_import_only():
    client = _power_client()
    pb = _power_by_day(client)
    s = pb.samples[0]
    assert s.solar == 0.0
    assert s.home == pytest.approx(1.13)          # grid -> home
    assert s.grid_import == pytest.approx(1.13 + 0.054)
    assert s.grid_export == 0.0
    assert s.battery_charge == pytest.approx(0.054)  # grid -> battery counts as charging


def test_power_by_day_short_arrays_are_padded():
    """A short result array must not crash or shift the later samples."""
    from .history_test import POWER_BY_DAY as RAW

    res = dict(RAW["result"])
    del res["powerGenHomeArray"]  # endpoint omits a whole channel
    client = _StubClient({"getFhpPowerByDay": res})
    pb = _power_by_day(client)
    assert len(pb.samples) == len(RAW["result"]["deviceTimeArray"])
    assert all(s.generator == 0.0 for s in pb.samples)


def test_power_by_day_requests_daytime_param():
    client = _power_client()
    _power_by_day(client)
    url, params = client.calls[0]
    assert url.endswith("api-energy/power/getFhpPowerByDay")
    assert params == {"dayTime": "2026-11-03"}


# ---- get_electric_daily ----------------------------------------------------------

def test_electric_daily_reads_scalar_per_channel():
    client = _electric_client()
    d = _electric_daily(client)
    assert d.day == "2026-11-03"
    assert d.solar == pytest.approx(20.979)
    assert d.grid_import == pytest.approx(34.18)
    assert d.grid_export == pytest.approx(11.373)
    assert d.battery_charge == pytest.approx(8.118)
    assert d.battery_discharge == pytest.approx(5.044)
    assert d.home == pytest.approx(42.461)
    assert d.v2l_export == 0.0 and d.v2l_import == 0.0


def test_electric_daily_missing_channel_is_zero():
    from .history_test import ELECTRIC_DAILY as RAW

    res = dict(RAW["result"])
    del res["kwhV2lToFhpArray"]
    client = _StubClient({"getFhpElectricData": res})
    d = _electric_daily(client)
    assert d.v2l_import == 0.0
    assert d.solar == pytest.approx(20.979)  # unaffected
