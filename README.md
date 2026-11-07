# franklinwh-python

Python bindings to the FranklinWH API, such as it is.

In order to use this, you'll need an access token, and your gateway ID. There's a bundled script which can generate an access token, your gateway ID can be found in the app under More -> Site Address. It's shown as your SN.

```bash
python3 -m pip install franklinwh
```

## Informational scripts

Scripts in [bin](./bin) use the API to show detailed information about your installation but have extra dependencies, install with

```bash
python3 -m pip install franklinwh[bin]
```

Most scripts require email address, password, and probably gateway id (referenced above).

```bash
python3 bin/get_info.py $FRANKLINWH_EMAIL $FRANKLINWH_PASSWORD $FRANKLINWH_GATEWAY_ID
```

## Historical data

The cloud keeps more than the gateway does. Two endpoints expose it (no
library wrapper yet -- see the open PR): `api-energy/power/getFhpPowerByDay`
for 5-minute power curves, and `api-energy/electric/getFhpElectricData`
for daily/weekly/monthly kWh totals. The app's "Download my data" CSV
export is the power-by-day data in CSV form.

```python
import asyncio
from datetime import date

from franklinwh import Client, TokenFetcher

async def main():
    client = Client(TokenFetcher(EMAIL, PASSWORD), GATEWAY_ID)
    await client.refresh_token()

    day = date(2026, 11, 3)
    power = await client.get_power_by_day(day.isoformat())
    for s in power.samples:      # 5-minute buckets, gateway-local time
        print(s.ts, f"solar={s.solar:.2f}kW home={s.home:.2f}kW soc={s.battery_soc:.1f}%")

    totals = await client.get_electric_daily(day.isoformat())
    print(f"solar={totals.solar} kWh imported={totals.grid_import} exported={totals.grid_export}")

asyncio.run(main())
```

Notes from real data:

- A day's `samples` may be shorter than 288: the gateway only emits 5-minute
  buckets once it has activity, and they start at the first reading, not
  midnight. Parse defensively.
- `PowerSample.kwh_total` is a running gateway figure, **not** a daily
  cumulative counter: it repeats across hours, lags changes, and the last
  bucket of a day still carries the previous day's final value. For day
  totals use `get_electric_daily()`.

## Development

The [Makefile](./Makefile) has a target to assist development and eventual release:

- `prepare` - run this once to install `franklinwh` in **editable mode** and prerequisites for bin and build.

This should be run in the context where you will eventually develop, which could be

- [franklinwh-python](#franklinwh-python)

  In this case a [virtual environment](https://www.w3schools.com/python/python_virtualenv.asp) is recommended.

  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  ```

- [Home Assistant Core](https://github.com/home-assistant/core) with [FranklinWH integration](https://github.com/richo/homeassistant-franklinwh)

  This has too many permutations to discuss here but is a primary use for this API.

```bash
make prepare
```

## Release

The [Makefile](./Makefile) has targets to assist the release process:

- `build` - build the distribution.
- `release` - upload to PyPi.

The release process involves these steps:

- bump and commit version

  [pyproject.toml/project/version](./pyproject.toml) must be unique and conform to [semantic versioning](https://semver.org/).

> [!NOTE]
> This may already be included in a [Pull Request](<https://github.com/richo/franklinwh-python/pulls>).

- build

  ```bash
  make build
  ```

  Fix any errors and commit the changes.

- upload

  ```bash
  make release
  ```
