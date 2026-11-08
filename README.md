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

### Raw API reference

The two endpoints return parallel arrays indexed by 5-minute bucket
position (for power) or day (for electric). All values are numeric; missing
channels are simply absent from the response, and individual elements can be
`null`.

#### `GET api-energy/power/getFhpPowerByDay?dayTime=YYYY-MM-DD`

Returns 5-minute power data for one day. 288 buckets in a full day
(00:00–23:55). All power values are **kW**.

| API field | Unit | Meaning |
|---|---|---|
| `deviceTimeArray` | — | ISO timestamps `"YYYY-MM-DD HH:MM:SS"`, 5-min intervals |
| `powerSolarHomeArray` | kW | Solar → home (direct consumption) |
| `powerSolarGirdArray` | kW | Solar → grid (export). "Gird" is the API's typo for "Grid". |
| `powerSolarFhpArray` | kW | Solar → battery (charging) |
| `powerGirdHomeArray` | kW | Grid → home (import) |
| `powerGirdFhpArray` | kW | Grid → battery (charging) |
| `powerFhpHomeArray` | kW | Battery → home (discharge) |
| `powerFhpGirdArray` | kW | Battery → grid (export) |
| `powerGenHomeArray` | kW | Generator → home |
| `powerGenFhpArray` | kW | Generator → battery |
| `powerV2lHomeArray` | kW | Vehicle → home |
| `powerV2lFhpArray` | kW | Vehicle → battery |
| `socArray` | % | Battery state of charge (0–100) |
| `kwhTotalArray` | kWh | Gateway's running home-energy figure. **Not** a daily cumulative. |
| `runStatusArray` | — | Gateway run status code (0 = normal) |

**Derived fields** the library computes from the raw channels:

| `PowerSample` field | Formula |
|---|---|
| `solar` | `powerSolarHome` + `powerSolarGird` + `powerSolarFhp` |
| `grid` / `grid_import` | `powerGirdHome` + `powerGirdFhp` |
| `grid_export` | `powerSolarGird` + `powerFhpGird` |
| `battery_discharge` | `powerFhpHome` + `powerFhpGird` |
| `battery_charge` | `powerSolarFhp` + `powerGirdFhp` |
| `generator` | `powerGenHome` + `powerGenFhp` |
| `v2l` | `powerV2lHome` + `powerV2lFhp` |
| `home` | `powerSolarHome` + `powerGirdHome` + `powerFhpHome` + `powerGenHome` + `powerV2lHome` |
| `battery_soc` | `socArray` |
| `kwh_total` | `kwhTotalArray` |
| `run_status` | `runStatusArray` |

#### `GET api-energy/electric/getFhpElectricData?type=1&dayTime=YYYY-MM-DD`

Returns daily energy totals (kWh). `type` values: 1=daily, 2=weekly,
3=monthly, 4=yearly, 5=all-time. All fields are single-element arrays
containing the cumulative value for the period.

| API field | Unit | Meaning |
|---|---|---|
| `deviceTimeArray` | — | Period label (e.g. `"2026-11-03"` for daily) |
| `kwhSuArray` | kWh | Solar production. "Su" = solar. |
| `kwhGenArray` | kWh | Generator production |
| `kwhUtiInArray` | kWh | Grid import. "Uti" = utility. |
| `kwhUtiOutArray` | kWh | Grid export |
| `kwhFhpChgArray` | kWh | Battery charging. "Fhp" = Franklin Home Power (battery). |
| `kwhFhpDiArray` | kWh | Battery discharge |
| `kwhLoadArray` | kWh | Home consumption |
| `kwhV2lToHomeArray` | kWh | Vehicle → home energy |
| `kwhV2lToFhpArray` | kWh | Home → vehicle energy |

**`ElectricDaily` mapping:** `solar` ← `kwhSuArray`, `generator` ←
`kwhGenArray`, `grid_import` ← `kwhUtiInArray`, `grid_export` ←
`kwhUtiOutArray`, `battery_charge` ← `kwhFhpChgArray`,
`battery_discharge` ← `kwhFhpDiArray`, `home` ← `kwhLoadArray`,
`v2l_export` ← `kwhV2lToHomeArray`, `v2l_import` ← `kwhV2lToFhpArray`.

All endpoints require a valid Bearer token from the FranklinWH cloud
(`POST api-user/user/auth/login` → `accessToken`).

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
