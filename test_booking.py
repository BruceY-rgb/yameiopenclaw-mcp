#!/usr/bin/env python3
import asyncio
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath('.')))

from src.api.client import OntuotuApiClient
from src.auth.manager import AuthManager
from src.workflow.orchestrator import WorkflowOrchestrator

async def test():
    api_client = OntuotuApiClient(
        base_url='https://sla.ontuotu.com',
        app_key='2110171300000008',
        app_secret='AWUJy70toNfnKcRpOlowEXMuxBeGArYL',
    )

    auth = AuthManager(api_client)
    workflow = WorkflowOrchestrator(api_client, auth)

    # 配置
    username = '5341746603814055936'
    password = 'T2BoPlKa7dkyAafr'
    from_city = 'PEK'
    to_city = 'TYO'
    from_date = '2026-03-30'

    print('=' * 60)
    print('国际机票预订测试: PEK -> TYO')
    print('=' * 60)
    print()

    # 步骤1: 登录
    print('[步骤1] 用户登录...')
    login_result = await workflow.login_user(username, password)
    if not login_result['success']:
        print(f'❌ 登录失败: {login_result["message"]}')
        return
    print(f'✅ 登录成功')
    print()

    # 步骤2: 查询航班
    print('[步骤2] 查询航班...')
    search_result = await workflow.search_intl_flights(
        from_city=from_city,
        to_city=to_city,
        from_date=from_date,
        trip_type=1,
        cabin='Y'
    )

    if not search_result['success']:
        print(f'❌ 航班查询失败: {search_result["message"]}')
        return

    flights = search_result.get('flights', [])
    serial_number = search_result.get('serialNumber', '')
    print(f'✅ 找到 {len(flights)} 个航班 (共 {search_result.get("total", 0)} 个)')
    print()

    # 显示前3个航班
    print('可选航班:')
    for i, flight in enumerate(flights[:5]):
        flight_id = flight.get('flightId', flight.get('flightID', 'N/A'))
        airline = flight.get('airlineEN', 'N/A')
        finance = flight.get('financeDetail', {}).get('financeList', [{}])[0]
        price = finance.get('salePrice', 'N/A')
        tax = finance.get('tax', 'N/A')
        dep_airport = flight.get('depAirport', 'N/A')
        arr_airport = flight.get('arrAirport', 'N/A')
        dep_time = flight.get('depTime', 'N/A')
        arr_time = flight.get('arrTime', 'N/A')

        print(f'  [{i+1}] {dep_airport} {dep_time} -> {arr_airport} {arr_time}')
        print(f'      航司: {airline} | 价格: ¥{price} + ¥{tax}税')
    print()

    # 选择第一个航班
    selected_flight = flights[0]
    print(f'选择航班: {selected_flight.get("depAirport")} -> {selected_flight.get("arrAirport")}')
    print()

    # 步骤3: 创建出行人
    print('[步骤3] 创建出行人...')
    passenger_result = await workflow.create_passenger(
        name='杨思行',
        passenger_type=0,  # 成人
        nationality='CN',
        id_type='0',  # 护照
        id_number='E12345678',
        id_expiration='2030-12-31',
        gender=1,  # 男
        birthday='1990-01-01',
        phone='13800138000'
    )

    if not passenger_result['success']:
        print(f'❌ 创建出行人失败: {passenger_result["message"]}')
        return

    passenger_id = passenger_result.get('passenger_id')
    print(f'✅ 出行人创建成功: ID={passenger_id}')
    print()

    # 步骤4: 下单
    print('[步骤4] 国际机票下单...')
    book_result = await workflow.book_intl_flight(
        flight_id=selected_flight.get('flightId', selected_flight.get('flightID', '')),
        serial_number=serial_number,
        passenger_ids=[passenger_id],
        contact_name='杨思行',
        contact_phone='13800138000',
        contact_email='test@example.com',
        flight_data=selected_flight,
        search_params=search_result.get('searchParams', {}),
    )

    print()
    if book_result['success']:
        print('=' * 60)
        print('✅ 预订成功!')
        print(f'订单ID: {book_result.get("order_id", "N/A")}')
        print('=' * 60)
    else:
        print('=' * 60)
        print(f'❌ 预订失败: {book_result.get("message", "未知错误")}')
        print('=' * 60)

    print()
    print('完整响应:')
    print(json.dumps(book_result, ensure_ascii=False, indent=2))

asyncio.run(test())
