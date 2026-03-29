#!/usr/bin/env python3
"""
调试脚本 - 测试国内航班查询
"""

import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.api.client import OntuotuApiClient


CONFIG = {
    "base_url": "https://sla.ontuotu.com",
    "app_key": "2110171300000008",
    "app_secret": "AWUJy70toNfnKcRpOlowEXMuxBeGArYL",
    "username": "5341746603814055936",
    "password": "T2BoPlKa7dkyAafr",
}


async def test_domestic_flight_search():
    """测试国内航班查询"""
    print("=" * 60)
    print("测试国内航班查询")
    print("=" * 60)

    api_client = OntuotuApiClient(
        base_url=CONFIG["base_url"],
        app_key=CONFIG["app_key"],
        app_secret=CONFIG["app_secret"],
    )

    # 登录
    print("\n[1] 用户登录...")
    login_resp = await api_client.login(
        username=CONFIG["username"],
        password=CONFIG["password"]
    )

    if isinstance(login_resp, str):
        token = login_resp
    else:
        token = login_resp.get("value", {}).get("token", "")

    api_client.set_token(token)
    print(f"✅ 登录成功, Token: {token[:50]}...")

    # 测试国内航班查询
    print("\n[2] 测试国内航班查询...")

    search_body = {
        "pageIndex": 1,
        "pageSize": 10,
        "applyResult": True,
        "isGetAddedValue": False,
        "isLoadmorePrice": False,
        "isLowestisPrice": True,
        "isSearchGwbook": True,
        "isOnlySchedule": False,
        "multiCabinCombination": False,
        "originDestinations": [
            {
                "departureAirportCode": "",
                "departureCityCode": "BJS",
                "departureDate": "2026-03-30",
                "destinationAirportCode": "",
                "destinationCityCode": "SHA",
                "earliestTime": "",
                "latestTime": "",
                "arrAirport": "",
                "arrCity": "SHA",
                "depAirport": "",
                "depCity": "BJS",
                "depDate": "2026-03-30",
            }
        ],
        "passengers": [{"passengerType": 0, "count": 1, "passengerCount": 1}],
        "isAsync": True,
        "isDirection": 0,
        "tripType": 1,
        "cabinTypes": ["0"],
    }

    print(f"请求参数: {json.dumps(search_body, ensure_ascii=False, indent=2)}")

    try:
        resp = await api_client.request(
            "POST",
            "/api/flight/searchFlights",
            json=search_body
        )
        print(f"\n响应: {json.dumps(resp, ensure_ascii=False, indent=2)}")

        if resp.get("code") == "000000":
            flights = resp.get("detail", {}).get("flightList", [])
            print(f"\n✅ 找到 {len(flights)} 个国内航班")
            return True
        else:
            print(f"\n❌ 查询失败: {resp.get('description', resp.get('message', '未知错误'))}")
            return False

    except Exception as e:
        print(f"\n❌ 请求失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    try:
        result = await test_domestic_flight_search()
        print("\n" + "=" * 60)
        if result:
            print("国内航班查询测试成功!")
        else:
            print("国内航班查询测试失败")
        print("=" * 60)
    except Exception as e:
        print(f"❌ 异常: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
