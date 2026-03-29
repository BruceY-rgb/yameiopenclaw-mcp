#!/usr/bin/env python3
"""
调试脚本 - 查看实际发送的请求
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


async def test_direct_request():
    """直接测试 API 请求"""
    print("=" * 60)
    print("直接测试 API 请求")
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
    print(f"✅ 登录成功")

    # 使用 MCP orchestrator 的 search_intl_flights 方法的参数格式
    print("\n[2] 测试国际航班查询（使用 MCP 参数格式）...")

    from_city = "BJS"
    to_city = "NYC"
    from_date = "2026-03-30"
    cabin_type = "0"

    search_params = {
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
                "departureCityCode": from_city,
                "departureDate": from_date,
                "destinationAirportCode": "",
                "destinationCityCode": to_city,
                "earliestTime": "",
                "latestTime": "",
                "arrAirport": "",
                "arrCity": to_city,
                "depAirport": "",
                "depCity": from_city,
                "depDate": from_date,
            }
        ],
        "passengers": [{"passengerType": 0, "count": 1, "passengerCount": 1}],
        "isAsync": True,
        "isDirection": 0,
        "tripType": 1,
        "cabinTypes": [cabin_type],
    }

    print(f"\n发送的请求:")
    print(json.dumps(search_params, ensure_ascii=False, indent=2))

    try:
        resp = await api_client.request(
            "POST",
            "/api/flight/intlsearch",
            json=search_params
        )
        print(f"\n响应:")
        print(json.dumps(resp, ensure_ascii=False, indent=2))

        if resp.get("code") == "000000":
            flights = resp.get("detail", {}).get("flightDetailList", [])
            print(f"\n✅ 找到 {len(flights)} 个航班")
            return flights
        else:
            print(f"\n❌ 查询失败: {resp.get('description', resp.get('message', '未知错误'))}")
            return []

    except Exception as e:
        print(f"\n❌ 请求失败: {e}")
        import traceback
        traceback.print_exc()
        return []


async def main():
    try:
        flights = await test_direct_request()
        print("\n" + "=" * 60)
        if flights:
            print(f"测试成功! 找到 {len(flights)} 个航班")
            for i, f in enumerate(flights[:3]):
                print(f"  [{i+1}] {f.get('flightId')} - {f.get('airline')}")
        else:
            print("测试失败")
        print("=" * 60)
    except Exception as e:
        print(f"❌ 异常: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
