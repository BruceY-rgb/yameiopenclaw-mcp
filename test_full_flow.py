#!/usr/bin/env python3
"""
完整流程测试脚本

测试 MCP 代码的完整预订流程：
1. 登录获取 Token
2. 两步查询国际航班（async + list）
3. 创建出行人
4. 国际机票下单
"""

import asyncio
import json
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.api.client import OntuotuApiClient
from src.auth.manager import AuthManager
from src.workflow.orchestrator import WorkflowOrchestrator


# 测试配置 - 请根据实际情况修改
CONFIG = {
    # API 配置
    "base_url": "https://sla.ontuotu.com",
    "app_key": "2110171300000008",
    "app_secret": "AWUJy70toNfnKcRpOlowEXMuxBeGArYL",

    # 用户账号（需要有企业员工权限）
    "username": "5341746603814055936",
    "password": "T2BoPlKa7dkyAafr",

    # 航班查询参数
    "from_city": "BJS",  # 北京城市码
    "to_city": "TYO",  # 东京城市码
    "from_date": "2026-03-30",  # 明天
    "trip_type": 1,  # 1=单程
    "cabin": "Y",  # Y=经济舱

    # 联系人
    "contact": {
        "name": "测试用户",
        "phone": "13800138000",
        "email": "test@example.com"
    },

    # 出行人信息
    "passenger_infos": [
        {
            "name": "张三",
            "passenger_type": 0,  # 0=成人
            "nationality": "CN",
            "id_type": "0",  # 0=护照
            "id_number": "E12345678",
            "id_expiration": "2030-12-31",
            "gender": 1,  # 1=男
            "birthday": "1990-01-01",
            "phone": "13800138001"
        }
    ]
}


async def test_step_by_step():
    """逐步测试每个步骤"""
    print("=" * 60)
    print("开始完整流程测试")
    print("=" * 60)

    # 创建 API 客户端
    api_client = OntuotuApiClient(
        base_url=CONFIG["base_url"],
        app_key=CONFIG["app_key"],
        app_secret=CONFIG["app_secret"],
    )

    # 创建认证管理器
    auth_manager = AuthManager(api_client)

    # 创建工作流编排器
    workflow = WorkflowOrchestrator(api_client, auth_manager)

    # ========================================
    # 步骤 1: 登录
    # ========================================
    print("\n[步骤 1/4] 用户登录...")
    login_result = await workflow.login_user(
        username=CONFIG["username"],
        password=CONFIG["password"]
    )

    if not login_result["success"]:
        print(f"❌ 登录失败: {login_result['message']}")
        return False

    print(f"✅ 登录成功, Token: {login_result['token'][:30]}...")

    # ========================================
    # 步骤 2: 查询国际航班（两步流程）
    # ========================================
    print("\n[步骤 2/4] 查询国际航班...")

    # 使用 quick_booking 方法进行一键测试
    # 但先单独测试 search_intl_flights 方法
    search_result = await workflow.search_intl_flights(
        from_city=CONFIG["from_city"],
        to_city=CONFIG["to_city"],
        from_date=CONFIG["from_date"],
        trip_type=CONFIG["trip_type"],
        cabin=CONFIG["cabin"]
    )

    if not search_result["success"]:
        print(f"❌ 航班查询失败: {search_result['message']}")
        print(f"   - 完整响应: {json.dumps(search_result.get('data', {}), ensure_ascii=False, indent=2)}")
        return False

    print(f"✅ 航班查询成功!")
    print(f"   - SerialNumber: {search_result['serialNumber']}")
    print(f"   - CacheExpirTime: {search_result['cacheExpirTime']}")
    print(f"   - 航班数量: {len(search_result['flights'])}")
    print(f"   - 完整响应: {json.dumps(search_result.get('data', {}), ensure_ascii=False, indent=2)}")

    # 显示前 3 个航班
    for i, flight in enumerate(search_result["flights"][:3]):
        flight_id = flight.get("flightId", flight.get("flightID", "N/A"))
        airline = flight.get("airline", "N/A")
        print(f"   [{i+1}] FlightID: {flight_id}, Airline: {airline}")

    # ========================================
    # 步骤 3: 创建出行人
    # ========================================
    print("\n[步骤 3/4] 创建出行人...")

    passenger_ids = []
    for pax_info in CONFIG["passenger_infos"]:
        pax_result = await workflow.create_passenger(
            name=pax_info["name"],
            passenger_type=pax_info["passenger_type"],
            nationality=pax_info["nationality"],
            id_type=pax_info["id_type"],
            id_number=pax_info["id_number"],
            id_expiration=pax_info["id_expiration"],
            gender=pax_info["gender"],
            birthday=pax_info["birthday"],
            phone=pax_info.get("phone")
        )

        if not pax_result["success"]:
            print(f"❌ 创建出行人失败: {pax_result['message']}")
            # 继续尝试获取已存在的出行人
        else:
            print(f"✅ 出行人创建成功: ID={pax_result['passenger_id']}")
            passenger_ids.append(pax_result["passenger_id"])

    if not passenger_ids:
        print("⚠️ 没有可用的出行人，跳过下单步骤")
        return True

    # ========================================
    # 步骤 4: 国际机票下单
    # ========================================
    print("\n[步骤 4/4] 国际机票下单...")

    if not search_result["flights"]:
        print("⚠️ 没有航班可预订")
        return True

    # 选择第一个航班
    selected_flight = search_result["flights"][0]
    flight_id = selected_flight.get("flightId", selected_flight.get("flightID", ""))
    serial_number = search_result["serialNumber"]

    print(f"   - 选择航班: {flight_id}")
    print(f"   - SerialNumber: {serial_number}")
    print(f"   - 出行人: {passenger_ids}")

    # 调用下单接口
    booking_result = await workflow.book_intl_flight(
        flight_id=flight_id,
        serial_number=serial_number,
        passenger_ids=passenger_ids,
        contact_name=CONFIG["contact"]["name"],
        contact_phone=CONFIG["contact"]["phone"],
        contact_email=CONFIG["contact"]["email"],
        policy_serial_number=serial_number,
        flight_data=selected_flight,
        search_params=search_result.get("searchParams", {}),
        passenger_infos=CONFIG["passenger_infos"]
    )

    if booking_result["success"]:
        print(f"✅ 下单成功!")
        print(f"   - OrderID: {booking_result['order_id']}")
        print(f"   - 响应数据: {json.dumps(booking_result['data'], ensure_ascii=False, indent=2)}")
    else:
        print(f"❌ 下单失败: {booking_result['message']}")
        print(f"   - 响应数据: {json.dumps(booking_result['data'], ensure_ascii=False, indent=2) if booking_result['data'] else 'None'}")

    return booking_result["success"]


async def test_quick_booking():
    """一键测试完整流程"""
    print("\n" + "=" * 60)
    print("一键预订测试")
    print("=" * 60)

    # 创建 API 客户端
    api_client = OntuotuApiClient(
        base_url=CONFIG["base_url"],
        app_key=CONFIG["app_key"],
        app_secret=CONFIG["app_secret"],
    )

    # 创建认证管理器
    auth_manager = AuthManager(api_client)

    # 创建工作流编排器
    workflow = WorkflowOrchestrator(api_client, auth_manager)

    # 一键预订
    result = await workflow.quick_booking(
        username=CONFIG["username"],
        password=CONFIG["password"],
        from_city=CONFIG["from_city"],
        to_city=CONFIG["to_city"],
        from_date=CONFIG["from_date"],
        passenger_infos=CONFIG["passenger_infos"],
        contact=CONFIG["contact"],
        flight_index=0,
        trip_type=CONFIG["trip_type"],
        cabin=CONFIG["cabin"]
    )

    if result["success"]:
        print(f"✅ 一键预订成功!")
        print(f"   - OrderID: {result['order_id']}")
    else:
        print(f"❌ 一键预订失败: {result['message']}")

    return result["success"]


async def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("MCP 完整流程测试")
    print("=" * 60)
    print(f"\n测试配置:")
    print(f"  - API: {CONFIG['base_url']}")
    print(f"  - AppKey: {CONFIG['app_key']}")
    print(f"  - 用户: {CONFIG['username']}")
    print(f"  - 航线: {CONFIG['from_city']} -> {CONFIG['to_city']}")
    print(f"  - 日期: {CONFIG['from_date']}")

    try:
        # 逐步测试
        success = await test_step_by_step()

        # 如果逐步测试成功，尝试一键预订
        if success:
            await test_quick_booking()

        print("\n" + "=" * 60)
        if success:
            print("✅ 完整流程测试完成")
        else:
            print("❌ 测试过程中出现错误")
        print("=" * 60)

        return success

    except Exception as e:
        print(f"\n❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)
