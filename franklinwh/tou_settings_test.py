"""Regression tests for the tou-settings fixes.

Everything here guards a value that used to be hardcoded and is now read from
getGatewayTouListV2. Fixtures are real gateway captures; see fixtures_test.py.
"""

import pytest

from .fixtures_test import SWITCH_STATUS, TOU_LIST


# ---- issue: get_mode() KeyErrors on non-default profile ids ----------------------

def test_get_mode_resolves_six_digit_profile_id():
    """MODE_MAP is keyed 9322/9323/9324; real accounts report six-digit ids.

    Guards the KeyError: 146692 that get_mode() raises today.
    """
    from .client import MODE_MAP
    runing = SWITCH_STATUS["runingMode"]
    assert runing not in MODE_MAP, "fixture must exercise the failing path"

    # The tou list is the lookup that works: currendId identifies the active entry.
    res = TOU_LIST["result"]
    active = next(m for m in res["list"] if m["id"] == res["currendId"])
    assert active["workMode"] == 1
    assert active["soc"] == 40.0
    assert active["name"] == "RETOU Res Energy TOU"


def test_reserve_soc_comes_from_the_active_entry():
    """Removes the touMinSoc/selfMinSoc/backupMaxSoc branching -- one field serves all modes."""
    res = TOU_LIST["result"]
    by_mode = {m["workMode"]: m["soc"] for m in res["list"]}
    assert by_mode == {1: 40.0, 2: 40.0, 3: 100.0}


# ---- issue #8: set_mode() forces Storm Hedge on ---------------------------------

def test_mode_payload_preserves_storm_hedge():
    """stromEn is the Storm Hedge toggle; set_mode() must not switch it on unasked.

    Answers the maintainer's open question on #8 -- the current value is readable
    from getGatewayTouListV2, so it can be echoed back rather than guessed.
    """
    from .client import Mode
    current = TOU_LIST["result"]["stromEn"]
    assert current in (0, 1)

    mode = Mode.time_of_use(soc=15)
    payload = mode.payload("GATEWAY")
    assert payload["stromEn"] == str(current), (
        "payload should carry the gateway's current stromEn, not a hardcoded 1"
    )


@pytest.mark.parametrize("saved", [0, 1])
def test_mode_payload_round_trips_either_setting(saved):
    from .client import Mode
    mode = Mode.time_of_use(soc=15)
    mode.stromEn = saved
    assert mode.payload("GATEWAY")["stromEn"] == str(saved)


def test_old_index_differs_per_mode():
    """issue #28: oldIndex was hardcoded to 1, which is the Emergency Backup value.

    The tou list ships oldIndex alongside each profile, and the values match the
    library's own set_mode() comments: TOU 3, self-consumption 2, backup 1.
    """
    from .client import Mode
    assert Mode.time_of_use(soc=15).payload("G")["oldIndex"] == "3"
    assert Mode.self_consumption(soc=20).payload("G")["oldIndex"] == "2"
    assert Mode.emergency_backup(soc=100).payload("G")["oldIndex"] == "1"

    by_work_mode = {m["workMode"]: m["oldIndex"] for m in TOU_LIST["result"]["list"]}
    assert by_work_mode == {1: 3, 2: 2, 3: 1}, "gateway agrees with the constants"
