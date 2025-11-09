#!/usr/bin/env python3
"""Get information about the FranklinHW installation."""

import argparse
import asyncio
import logging
import sys
import time

from franklinwh import Client, TokenFetcher
import jsonpickle


async def main():
    """Do all the work."""
    parser = argparse.ArgumentParser(description="Get FranklinWH installation info.")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging.",
    )
    parser.add_argument(
        "username",
        type=str,
        help="The username for the installation.",
    )
    parser.add_argument(
        "password",
        type=str,
        help="The password for the installation.",
    )
    parser.add_argument(
        "gateway",
        type=str,
        help="The gateway / serial number to query.",
    )

    args = parser.parse_args()

    if args.debug:
        logging.basicConfig()
        logging.getLogger("franklinwh").setLevel(logging.DEBUG)
        logging.getLogger("httpx").setLevel(logging.DEBUG)

    fetcher = TokenFetcher(args.username, args.password)
    client = Client(fetcher, args.gateway)
    await client.refresh_token()  # populate fetcher.info
    assert fetcher.info is not None
    dayTime = time.strftime("%Y-%m-%d")

    functions = {
        "api-energy/electric/getFhpElectricData": {"type": 1, "dayTime": dayTime},
        "hes-gateway/common/getAccessoryList": None,
        "hes-gateway/common/getPageByTypeList": {
            "typeList": "sdcpSwitchModeTip,modeListPageVppTip,modeListPageVppExitTip"
        },
        "hes-gateway/common/getPowerCapConfigList": None,
        "hes-gateway/common/selectDeviceRunLogList": None,
        "hes-gateway/terminal/appObtainAdvertiseLst": None,
        "hes-gateway/terminal/backupHistorySummary": None,
        "hes-gateway/terminal/bill/electric/selectBenefitInfo": {
            "type": 1,
            "dayTime": dayTime,
        },
        "hes-gateway/terminal/chargePowerDetails": None,
        "hes-gateway/terminal/getAppGlobalConfig": {"userId": fetcher.info["userId"]},
        "hes-gateway/terminal/getDeviceCompositeInfo": {"refreshFlag": 0},
        "hes-gateway/terminal/getDeviceInfoV2": None,
        "hes-gateway/terminal/getGatewaySystemSetting": None,
        "hes-gateway/terminal/getHomeGatewayList": None,
        "hes-gateway/terminal/getHotSpotInfo/v2": None,
        "hes-gateway/terminal/getPersonalInfo": None,
        "hes-gateway/terminal/getShowTip": {"type": 1},
        "hes-gateway/terminal/message/selectMessage": None,
        "hes-gateway/terminal/newCompliance/getComplianceDetailById": {"systemId": 0},
        "hes-gateway/terminal/newCompliance/getComplianceNameList": None,
        "hes-gateway/terminal/obtainAgateInfo": None,
        "hes-gateway/terminal/obtainApowersInfo": None,
        "hes-gateway/terminal/queryProgramDetails": None,
        "hes-gateway/terminal/recommend/recommendFlag": None,
        "hes-gateway/terminal/selectDeviceOverallInfo": None,
        "hes-gateway/terminal/selectGatewayAlarm": None,
        "hes-gateway/terminal/selectIotGenerator": None,
        "hes-gateway/terminal/selectOffgrid": {"type": 0},
        "hes-gateway/terminal/selectProgramFlag": None,
        "hes-gateway/terminal/selectSimBtn": None,
        "hes-gateway/terminal/selectTerPushMessageUnreadCount": None,
        "hes-gateway/terminal/site/get/DeviceDetail": None,
        "hes-gateway/terminal/site/list/siteAndDeviceInfo": {
            "pageNum": 1,
            "pageSize": 10,
            "userAccount": args.username,
            "userId": fetcher.info["userId"],
        },
        "hes-gateway/terminal/solar/selectAnyOneSolarOpen": None,
        "hes-gateway/terminal/span/getSpanSetting": None,
        "hes-gateway/terminal/tou/getBonusInfo": None,
        "hes-gateway/terminal/tou/getEntranceInfo": None,
        "hes-gateway/terminal/tou/getGatewayTouListV2": {"showType": 1},
        "hes-gateway/terminal/tou/getPowerControlSetting": None,
        "hes-gateway/terminal/tou/getTouDispatchDetail": None,
        "hes-gateway/terminal/weather/getCurrentBriefWeather": {"equipNo": args},
        "hes-gateway/terminal/weather/getProgressingStormList": {
            "equipNo": args.gateway
        },
        "hes-gateway/terminal/weather/getStormSetting": {"equipNo": args.gateway},
        "_status": None,
        "_switch_status": None,
        "_switch_usage": None,
        "get_accessories": None,
        # "get_mode": None, # KeyError: 21669
        "get_smart_switch_state": None,
        "get_stats": None,
    }

    async def get(func: str) -> None:
        if func.endswith("/getGatewayTouListV2"):
            return (await client._post(client.url_base + func, None, functions[func]))["result"]  # noqa: SLF001
        if func.startswith(("api-energy", "hes-gateway")):
            return (await client._get(client.url_base + func, functions[func]))["result"]  # noqa: SLF001
        return await getattr(client, func)()

    async def async_get(func: str) -> None:
        functions[func] = await get(func)

    tasks = [async_get(func) for func in functions]
    await asyncio.gather(*tasks)

    print(jsonpickle.dumps(functions, indent=2, unpicklable=False))  # noqa: T201

    sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
