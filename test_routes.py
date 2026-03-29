#!/usr/bin/env python3
import asyncio
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath('.')))

from src.api.client import OntuotuApiClient
from src.auth.manager import AuthManager

async def test():
    api_client = OntuotuApiClient(
        base_url='https://sla.ontuotu.com',
        app_key='2110171300000008',
        app_secret='AWUJy70toNfnKcRpOlowEXMuxBeGArYL',
    )

    auth = AuthManager(api_client)
    token = await auth.get_token('5341746603814055936', 'T2BoPlKa7dkyAafr')
    print('登录成功')
    print()

    routes = [
        {'name': 'PEK->TYO', 'dep': 'PEK', 'arr': 'TYO'},
        {'name': 'PVG->TYO', 'dep': 'PVG', 'arr': 'TYO'},
        {'name': 'SHA->TYO', 'dep': 'SHA', 'arr': 'TYO'},
        {'name': 'PEK->SEL', 'dep': 'PEK', 'arr': 'SEL'},
        {'name': 'PVG->SEL', 'dep': 'PVG', 'arr': 'SEL'},
        {'name': 'PEK->HKG', 'dep': 'PEK', 'arr': 'HKG'},
        {'name': 'PVG->HKG', 'dep': 'PVG', 'arr': 'HKG'},
        {'name': 'PEK->SIN', 'dep': 'PEK', 'arr': 'SIN'},
        {'name': 'PVG->SIN', 'dep': 'PVG', 'arr': 'SIN'},
        {'name': 'PEK->SYD', 'dep': 'PEK', 'arr': 'SYD'},
        {'name': 'PVG->SYD', 'dep': 'PVG', 'arr': 'SYD'},
        {'name': 'PEK->LAX', 'dep': 'PEK', 'arr': 'LAX'},
        {'name': 'PVG->LAX', 'dep': 'PVG', 'arr': 'LAX'},
        {'name': 'PEK->SFO', 'dep': 'PEK', 'arr': 'SFO'},
        {'name': 'PVG->SFO', 'dep': 'PVG', 'arr': 'SFO'},
    ]

    print('=== 测试各航线 (2026-03-30) ===')
    print()

    available = []

    for route in routes:
        search_params = {
            'isDirection': 0,
            'isAsync': True,
            'originDestinations': [{
                'depAirport': route['dep'],
                'depDate': '2026-03-30',
                'arrAirport': route['arr']
            }],
            'cabinTypes': ['0'],
            'passengers': [{'count': 1, 'passengerType': '0'}]
        }

        resp1 = await api_client.search_intl_flights(search_params)
        if resp1.get('code') != '000000':
            print(f'查询失败: {route["name"]}')
            continue

        serial_number = resp1.get('detail', {}).get('serialNumber', '')

        await asyncio.sleep(3)

        resp2 = await api_client.search_intl_flights_async({
            'serialNumber': serial_number,
            'pageIndex': 1,
            'pageSize': 5
        })

        if resp2.get('code') == '000000':
            total = resp2.get('total', 0)
            if total > 0:
                first_flight = resp2.get('detail', {}).get('flightDetailList', [{}])[0]
                price = first_flight.get('financeDetail', {}).get('financeList', [{}])[0].get('salePrice', 'N/A')
                airline = first_flight.get('airlineEN', 'N/A')

                print(f'✅ {route["name"]}: {total} 个航班 | 最低价: ¥{price} ({airline})')
                available.append({
                    'name': route['name'],
                    'total': total,
                    'price': price,
                    'airline': airline
                })
            else:
                print(f'❌ {route["name"]}: 无航班')
        else:
            print(f'❌ {route["name"]}: 获取失败')

    print()
    print(f'=== 汇总: {len(available)} 条可用航线 ===')
    for r in available:
        print(f'  {r["name"]}: {r["total"]} 航班, ¥{r["price"]}起 ({r["airline"]})')

asyncio.run(test())
