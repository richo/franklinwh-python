"""Test script for get_mode_settings(), get_mode() and set_mode_reserve().

Run from the franklinwh-python directory:
    python3 bin/test-tou-reserve.py <username> <password> <gateway_id>

What it does:
  1. Calls get_mode_settings() — prints all modes and reserves
  2. Calls get_mode()          — prints current mode via the new path
  3. Calls set_mode_reserve()  — writes back the SAME value (no visible change)

Nothing destructive: the set call uses whatever value is already stored.
"""

import asyncio
import sys
import os

# Run against the local source tree, not the installed PyPI package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import franklinwh
from franklinwh.client import WORK_MODE_MAP


async def main(username: str, password: str, gateway: str) -> None:
    fetcher = franklinwh.TokenFetcher(username, password)
    client = franklinwh.Client(fetcher, gateway)

    # ── 1. get_mode_settings() ───────────────────────────────────────────────
    print("\n── get_mode_settings() ─────────────────────────────────────────")
    settings = await client.get_mode_settings()
    print(f"  current_mode_id  : {settings.current_mode_id}")
    print(f"  current_work_mode: {settings.current_work_mode} "
          f"({WORK_MODE_MAP.get(settings.current_work_mode, '?')})")
    print(f"  reserves         : {settings.reserves}")
    print("  modes:")
    for m in settings.modes:
        active = " ← active" if m.id == settings.current_mode_id else ""
        editable = "editable" if m.edit_soc_flag else "read-only"
        print(f"    workMode={m.work_mode}  id={m.id:6d}  soc={m.soc:5.1f}%"
              f"  {editable:9s}  name={m.name!r}{active}")

    # ── 2. get_mode() ────────────────────────────────────────────────────────
    print("\n── get_mode() ──────────────────────────────────────────────────")
    mode_name, soc = await client.get_mode()
    print(f"  mode_name: {mode_name!r}")
    print(f"  soc      : {soc}%")

    # ── 3. set_mode_reserve() — write back the existing value ────────────────
    active_wm = settings.current_work_mode
    if active_wm in settings.reserves:
        current_soc = int(settings.reserves[active_wm])
        mode_label = WORK_MODE_MAP.get(active_wm, "?")
        print(f"\n── set_mode_reserve(work_mode={active_wm}, soc={current_soc}) "
              f"[{mode_label}, no-op] ───")
        if active_wm == 3:
            print("  Skipping Emergency Backup (editSocFlag=false, server will reject)")
        else:
            await client.set_mode_reserve(active_wm, current_soc)
            print("  ✓ Success — value written back unchanged")

            # Confirm by re-reading
            confirm = await client.get_mode_settings()
            confirmed_soc = confirm.reserves.get(active_wm)
            match = "✓" if confirmed_soc == current_soc else "✗ MISMATCH"
            print(f"  {match} Confirmed reserve still {confirmed_soc}%")
    else:
        print("\n  Could not determine active work mode — skipping set test")

    print("\n── All tests passed ────────────────────────────────────────────\n")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(f"Usage: {sys.argv[0]} <username> <password> <gateway_id>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1], sys.argv[2], sys.argv[3]))
