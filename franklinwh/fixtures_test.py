"""Fixtures captured from a live gateway (V1.12.45, System 1.5, 3x aPower).

Serial numbers scrubbed. Trimmed to the fields under test.
"""

# tou/getGatewayTouListV2 -- note the six-digit profile ids. MODE_MAP's 9322/9323/9324
# do not appear on this account, which is what breaks get_mode().
TOU_LIST = {
    "code": 200,
    "result": {
        "currendId": 146692,
        "list": [
            {"id": 146692, "workMode": 1, "name": "RETOU Res Energy TOU", "soc": 40.0,
             "maxSoc": 100.0, "minSoc": 5.0, "oldIndex": 3},
            {"id": 195208, "workMode": 2, "name": "Self-Consumption", "soc": 40.0,
             "maxSoc": 100.0, "minSoc": 5.0, "oldIndex": 2},
            {"id": 222416, "workMode": 3, "name": "Emergency Backup", "soc": 100.0,
             "maxSoc": 100.0, "minSoc": 5.0, "oldIndex": 1},
        ],
        "stromEn": 1,
        "zoneInfo": "America/Denver",
        "tariffName": "RETOU Res Energy TOU",
    },
    "success": True,
}

# _switch_status(): runingMode carries the same id as currendId.
SWITCH_STATUS = {"runingMode": 146692, "touMinSoc": 40, "selfMinSoc": 40, "backupMaxSoc": 100}
