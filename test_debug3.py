#!/usr/bin/env python3
"""
调试脚本 - 尝试查询可用航线
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


async def test_search_with_different_params():
    """测试不同参数组合"""
    print("=" * 60)
    print("测试不同查询参数组合")
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

    # 测试1: 简化参数
    print("\n[2] 测试1: 简化参数 + isDirection...")

    simple_params = {
        "tripType": 1,
        "fromCity": "BJS",
        "toCity": "SEL",
        "fromDate": "2026-03-29",
        "adultCount": 1,
        "isDirection": 0,
    }

    print(f"参数: {json.dumps(simple_params, ensure_ascii=False)}")

    try:
        resp = await api_client.request(
            "POST",
            "/api/flight/intlsearch",
            json=simple_params
        )
        print(f"响应: {json.dumps(resp, ensure_ascii=False, indent=2)}")
    except Exception as e:
        print(f"请求失败: {e}")

    # 测试2: 使用完整参数格式（参考 Vue）
    print("\n[3] 测试2: 完整参数格式 BJS -> SEL (字符串乘客类型)...")

    params2 = {
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
                "departureDate": "2026-03-29",
                "destinationAirportCode": "",
                "destinationCityCode": "SEL",
                "earliestTime": "",
                "latestTime": "",
                "arrAirport": "",
                "arrCity": "SEL",
                "depAirport": "",
                "depCity": "BJS",
                "depDate": "2026-03-29",
            }
        ],
        "passengers": [{"passengerType": "ADT", "count": 1, "passengerCount": 1}],  # 字符串类型
        "isAsync": True,
        "isDirection": 0,
        "tripType": 1,
        "cabinTypes": ["0"],
    }

    print(f"参数: {json.dumps(params2, ensure_ascii=False)}")

    try:
        resp = await api_client.request(
            "POST",
            "/api/flight/intlsearch",
            json=params2
        )
        print(f"响应: {json.dumps(resp, ensure_ascii=False, indent=2)}")
    except Exception as e:
        print(f"请求失败: {e}")

    # 测试3: 完整参数格式 - 今天
    print("\n[4] 测试3: 完整参数格式 今天 BJS -> SEL (字符串乘客类型)...")

    params3 = {
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
                "departureDate": "2026-03-29",
                "destinationAirportCode": "",
                "destinationCityCode": "SEL",
                "earliestTime": "",
                "latestTime": "",
                "arrAirport": "",
                "arrCity": "SEL",
                "depAirport": "",
                "depCity": "BJS",
                "depDate": "2026-03-29",
            }
        ],
        "passengers": [{"passengerType": "ADT", "count": 1, "passengerCount": 1}],  # 字符串类型
        "isAsync": True,
        "isDirection": 0,
        "tripType": 1,
        "cabinTypes": ["0"],
    }

    print(f"参数: {json.dumps(params3, ensure_ascii=False)}")

    try:
        resp = await api_client.request(
            "POST",
            "/api/flight/intlsearch",
            json=params3
        )
        print(f"响应: {json.dumps(resp, ensure_ascii=False, indent=2)}")
    except Exception as e:
        print(f"请求失败: {e}")

    # 测试4: 完整参数格式 - 东京
    print("\n[5] 测试4: 完整参数格式 BJS -> TYO (字符串乘客类型)...")

    params4 = {
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
                "departureDate": "2026-03-29",
                "destinationAirportCode": "",
                "destinationCityCode": "TYO",
                "earliestTime": "",
                "latestTime": "",
                "arrAirport": "",
                "arrCity": "TYO",
                "depAirport": "",
                "depCity": "BJS",
                "depDate": "2026-03-29",
            }
        ],
        "passengers": [{"passengerType": "ADT", "count": 1, "passengerCount": 1}],  # 字符串类型
        "isAsync": True,
        "isDirection": 0,
        "tripType": 1,
        "cabinTypes": ["0"],
    }

    print(f"参数: {json.dumps(params4, ensure_ascii=False)}")

    try:
        resp = await api_client.request(
            "POST",
            "/api/flight/intlsearch",
            json=params4
        )
        print(f"响应: {json.dumps(resp, ensure_ascii=False, indent=2)}")
    except Exception as e:
        print(f"请求失败: {e}")


async def main():
    try:
        await test_search_with_different_params()
        print("\n" + "=" * 60)
        print("测试完成")
        print("=" * 60)
    except Exception as e:
        print(f"❌ 异常: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
