# getFhpPowerByDay -- captured from a live account. Trimmed to the fields under
# test, but the shapes (288 x 5-minute, gateway-local time, arrays of the same
# length) are the real ones. The first ~6 hours carry no solar and no gateway
# activity: the gateway only starts reporting 5-minute buckets once it has a
# reading, so early-morning rows are all zero and soc is stuck at the last
# reported value. This is the same shape the app's "Download my data" CSV has.
POWER_BY_DAY = {
    "code": 200,
    "result": {
        "deviceTimeArray": [
            "2026-11-03 00:00:00", "2026-11-03 00:05:00", "2026-11-03 00:10:00",
            "2026-11-03 08:55:00", "2026-11-03 09:00:00", "2026-11-03 09:05:00",
        ],
        "powerSolarHomeArray": [0, 0, 0, 0.0, 1.812, 1.794],
        "powerSolarGirdArray": [0, 0, 0, 0.0, 1.144, 1.155],
        "powerSolarFhpArray": [0.0, 0.0, 0.0, 0.0, 0.013, 0.011],
        "powerGirdHomeArray": [1.13, 0.615, 0.773, 0.58, 0, 0],
        "powerGirdFhpArray": [0.054, 0.056, 0.059, 0.057, 0, 0],
        "powerFhpHomeArray": [0, 0, 0, 0, 0, 0],
        "powerFhpGirdArray": [0, 0, 0, 0, 0, 0],
        "powerGenHomeArray": [0, 0, 0, 0, 0, 0],
        "powerGenFhpArray": [0, 0, 0, 0, 0, 0],
        "powerV2lHomeArray": [0, 0, 0, 0, 0, 0],
        "powerV2lFhpArray": [0, 0, 0, 0, 0, 0],
        "socArray": [99.789, 99.789, 99.789, 99.8, 99.8, 99.8],
        "kwhTotalArray": [44.905, 44.905, 44.905, 44.905, 44.9, 44.9],
        "runStatusArray": [0, 0, 0, 0, 0, 0],
    },
    "success": True,
}

# getFhpElectricData type=1 (daily totals) -- one element per requested day.
ELECTRIC_DAILY = {
    "code": 200,
    "result": {
        "deviceTimeArray": ["2026-11-03"],
        "kwhSuArray": [20.979],
        "kwhGenArray": [0.0],
        "kwhUtiInArray": [34.18],
        "kwhUtiOutArray": [11.373],
        "kwhFhpChgArray": [8.118],
        "kwhFhpDiArray": [5.044],
        "kwhLoadArray": [42.461],
        "kwhV2lToHomeArray": [0.0],
        "kwhV2lToFhpArray": [0.0],
    },
    "success": True,
}
