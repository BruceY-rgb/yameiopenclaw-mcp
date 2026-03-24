"""
Pytest配置文件

提供测试夹具和共享配置
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from typing import Dict, Any

from src.api.client import MeiyaApiClient
from src.auth.manager import AuthManager, TokenInfo
from src.workflow.orchestrator import WorkflowOrchestrator


# ===========================================
# Pytest配置
# ===========================================

def pytest_configure(config):
    """Pytest配置"""
    config.addinivalue_line(
        "markers", "asyncio: mark test as async test"
    )


# ===========================================
# 异步事件循环配置
# ===========================================

@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ===========================================
# API客户端夹具
# ===========================================

@pytest.fixture
def mock_httpx_response():
    """创建模拟的HTTP响应"""
    def _create_response(
        status_code: int = 200,
        json_data: Dict[str, Any] = None
    ):
        response = MagicMock()
        response.status_code = status_code
        response.json.return_value = json_data or {}
        response.raise_for_status = MagicMock()
        if status_code >= 400:
            response.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
        return response
    return _create_response


@pytest.fixture
def api_client():
    """创建API客户端实例（使用测试配置）"""
    return MeiyaApiClient(
        base_url="https://api.test.meiya.com",
        username="test_user",
        password="test_password",
        timeout=30.0,
        max_retries=3
    )


@pytest.fixture
def mock_api_client():
    """创建模拟的API客户端"""
    client = AsyncMock(spec=MeiyaApiClient)
    client.base_url = "https://api.test.meiya.com"
    client.username = "test_user"
    return client


# ===========================================
# 认证管理器夹具
# ===========================================

@pytest.fixture
def auth_manager(mock_api_client):
    """创建认证管理器实例"""
    return AuthManager(api_client=mock_api_client)


@pytest.fixture
def mock_token_info():
    """创建模拟的Token信息"""
    import time
    return TokenInfo(
        access_token="mock_access_token_12345",
        refresh_token="mock_refresh_token_67890",
        expires_at=time.time() + 7200,  # 2小时后过期
        token_type="Bearer",
        user_id="test_user"
    )


# ===========================================
# 工作流编排器夹具
# ===========================================

@pytest.fixture
def workflow_orchestrator(mock_api_client):
    """创建工作流编排器实例"""
    return WorkflowOrchestrator(api_client=mock_api_client)


# ===========================================
# 测试数据夹具
# ===========================================

@pytest.fixture
def sample_flight_data():
    """示例航班数据"""
    return {
        "code": 0,
        "message": "success",
        "data": {
            "flights": [
                {
                    "flightId": "FL123456",
                    "flightNumber": "CA981",
                    "airline": "CA",
                    "origin": "PEK",
                    "destination": "JFK",
                    "departureTime": "2026-04-01 13:00",
                    "arrivalTime": "2026-04-01 14:30",
                    "cabinClass": "economy",
                    "price": 5000.00,
                    "currency": "CNY"
                }
            ],
            "searchId": "search_abc123"
        }
    }


@pytest.fixture
def sample_passenger_data():
    """示例出行人数据"""
    return {
        "code": 0,
        "message": "success",
        "data": {
            "passengerId": "PAX123456",
            "name": "张三",
            "passengerType": "adult",
            "nationality": "CN",
            "idType": "0",
            "idNumber": "E12345678",
            "idExpiration": "2030-01-01",
            "gender": "1",
            "birthday": "1990-01-01"
        }
    }


@pytest.fixture
def sample_order_data():
    """示例订单数据"""
    return {
        "code": 0,
        "message": "success",
        "data": {
            "orderId": "ORD987654",
            "status": "created",
            "totalAmount": 5000.00,
            "currency": "CNY",
            "paymentUrl": "https://pay.test.com/pay",
            "pnr": "ABC123"
        }
    }


@pytest.fixture
def sample_pricing_data():
    """示例计价数据"""
    return {
        "code": 0,
        "message": "success",
        "data": {
            "policySerialNumber": "POL789012",
            "flightId": "FL123456",
            "cabinClass": "economy",
            "adultPrice": 5000.00,
            "adultTax": 500.00,
            "totalPrice": 5500.00,
            "currency": "CNY"
        }
    }


# ===========================================
# Mock API响应夹具
# ===========================================

@pytest.fixture
def mock_search_flights_success(sample_flight_data):
    """模拟航班搜索成功响应"""
    async def mock_request(*args, **kwargs):
        return sample_flight_data
    return mock_request


@pytest.fixture
def mock_create_passenger_success(sample_passenger_data):
    """模拟创建出行人成功响应"""
    async def mock_request(*args, **kwargs):
        return sample_passenger_data
    return mock_request


@pytest.fixture
def mock_create_order_success(sample_order_data):
    """模拟创建订单成功响应"""
    async def mock_request(*args, **kwargs):
        return sample_order_data
    return mock_request


@pytest.fixture
def mock_pricing_success(sample_pricing_data):
    """模拟计价成功响应"""
    async def mock_request(*args, **kwargs):
        return sample_pricing_data
    return mock_request
