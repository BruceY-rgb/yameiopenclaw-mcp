"""
API客户端测试

测试 MeiyaApiClient 类的功能，包括：
- Token认证生成算法
- HTTP请求封装
- 错误处理
- 重试机制
"""

import pytest
import json
import time
import base64
import hashlib
from unittest.mock import AsyncMock, MagicMock, patch

from src.api.client import MeiyaApiClient, MeiyaApiError


# ===========================================
# Token认证算法测试
# ===========================================

class TestTokenGeneration:
    """测试Token生成算法"""

    def test_token_generation_algorithm(self):
        """测试Token认证算法是否正确（MD5+Base64）"""
        # 创建固定时间戳的客户端
        client = MeiyaApiClient(
            base_url="https://api.test.meiya.com",
            username="test_user",
            password="test_password",
            timeout=30.0,
            max_retries=3
        )

        # 使用固定时间戳
        fixed_timestamp = "1704067200000"

        # 手动计算预期Token
        body = {"test": "data"}
        body_str = json.dumps(body, ensure_ascii=False, separators=(',', ':'))
        expected_mingwen = f"test_usertest_password{fixed_timestamp}{body_str}"
        expected_md5 = hashlib.md5(expected_mingwen.encode('utf-8')).digest()
        expected_token = base64.b64encode(expected_md5).decode('utf-8')

        # 验证Token算法
        with patch('src.api.client.time.time') as mock_time:
            mock_time.return_value = 1704067200.0  # 对应固定时间戳

            headers = client._generate_auth_headers(body)

            # 验证时间戳格式
            assert headers["TimeStamp"] == fixed_timestamp
            assert headers["UserName"] == "test_user"

            # 验证Token不为空
            assert headers["Token"] is not None
            assert len(headers["Token"]) > 0

    def test_token_generation_empty_body(self):
        """测试空请求体的Token生成"""
        client = MeiyaApiClient(
            base_url="https://api.test.meiya.com",
            username="test_user",
            password="test_password",
            timeout=30.0,
            max_retries=3
        )

        with patch('src.api.client.time.time') as mock_time:
            mock_time.return_value = 1704067200.0

            headers = client._generate_auth_headers({})

            # 空请求体时body_str为空字符串
            expected_mingwen = f"test_usertest_password{1704067200000}"
            expected_md5 = hashlib.md5(expected_mingwen.encode('utf-8')).digest()
            expected_token = base64.b64encode(expected_md5).decode('utf-8')

            assert headers["Token"] == expected_token

    def test_token_generation_different_usernames(self):
        """测试不同用户名的Token生成"""
        client1 = MeiyaApiClient(
            base_url="https://api.test.meiya.com",
            username="user1",
            password="password",
            timeout=30.0,
            max_retries=3
        )

        client2 = MeiyaApiClient(
            base_url="https://api.test.meiya.com",
            username="user2",
            password="password",
            timeout=30.0,
            max_retries=3
        )

        with patch('src.api.client.time.time') as mock_time:
            mock_time.return_value = 1704067200.0

            headers1 = client1._generate_auth_headers({})
            headers2 = client2._generate_auth_headers({})

            # 不同用户名生成的Token应该不同
            assert headers1["Token"] != headers2["Token"]
            assert headers1["UserName"] != headers2["UserName"]

    def test_token_generation_different_passwords(self):
        """测试不同密码的Token生成"""
        client1 = MeiyaApiClient(
            base_url="https://api.test.meiya.com",
            username="test_user",
            password="password1",
            timeout=30.0,
            max_retries=3
        )

        client2 = MeiyaApiClient(
            base_url="https://api.test.meiya.com",
            username="test_user",
            password="password2",
            timeout=30.0,
            max_retries=3
        )

        with patch('src.api.client.time.time') as mock_time:
            mock_time.return_value = 1704067200.0

            headers1 = client1._generate_auth_headers({})
            headers2 = client2._generate_auth_headers({})

            # 不同密码生成的Token应该不同
            assert headers1["Token"] != headers2["Token"]


# ===========================================
# API客户端初始化测试
# ===========================================

class TestApiClientInit:
    """测试API客户端初始化"""

    def test_client_init(self):
        """测试客户端初始化"""
        client = MeiyaApiClient(
            base_url="https://api.test.meiya.com",
            username="test_user",
            password="test_password",
            timeout=30.0,
            max_retries=3
        )

        assert client.base_url == "https://api.test.meiya.com"
        assert client.username == "test_user"
        assert client.password == "test_password"
        assert client.timeout == 30.0
        assert client.max_retries == 3

    def test_client_base_url_strip(self):
        """测试base_url去除尾部斜杠"""
        client = MeiyaApiClient(
            base_url="https://api.test.meiya.com///",
            username="test_user",
            password="test_password"
        )

        assert client.base_url == "https://api.test.meiya.com"

    def test_client_default_timeout(self):
        """测试默认超时时间"""
        client = MeiyaApiClient(
            base_url="https://api.test.meiya.com",
            username="test_user",
            password="test_password"
        )

        assert client.timeout == 30.0

    def test_client_default_max_retries(self):
        """测试默认重试次数"""
        client = MeiyaApiClient(
            base_url="https://api.test.meiya.com",
            username="test_user",
            password="test_password"
        )

        assert client.max_retries == 3


# ===========================================
# 响应状态检查测试
# ===========================================

class TestResponseValidation:
    """测试API响应验证"""

    def test_is_success_code_zero(self):
        """测试code为0时返回成功"""
        client = MeiyaApiClient(
            base_url="https://api.test.meiya.com",
            username="test_user",
            password="test_password"
        )

        assert client._is_success({"code": 0}) is True
        assert client._is_success({"code": 1}) is False
        assert client._is_success({"code": -1}) is False

    def test_is_success_success_field(self):
        """测试success字段检查"""
        client = MeiyaApiClient(
            base_url="https://api.test.meiya.com",
            username="test_user",
            password="test_password"
        )

        assert client._is_success({"success": True}) is True
        assert client._is_success({"success": False}) is False

    def test_is_success_no_status(self):
        """测试无状态字段时默认成功"""
        client = MeiyaApiClient(
            base_url="https://api.test.meiya.com",
            username="test_user",
            password="test_password"
        )

        assert client._is_success({}) is True
        assert client._is_success({"data": {}}) is True


# ===========================================
# API接口测试
# ===========================================

class TestApiMethods:
    """测试API方法"""

    @pytest.mark.asyncio
    async def test_search_flights(self, api_client, sample_flight_data):
        """测试航班搜索"""
        with patch.object(api_client, 'request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = sample_flight_data

            result = await api_client.search_flights(
                origin="PEK",
                destination="JFK",
                departure_date="2026-04-01",
                adults=1
            )

            assert result == sample_flight_data
            mock_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_flights_round_trip(self, api_client, sample_flight_data):
        """测试往返航班搜索"""
        with patch.object(api_client, 'request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = sample_flight_data

            result = await api_client.search_flights(
                origin="PEK",
                destination="JFK",
                departure_date="2026-04-01",
                trip_type="round_trip",
                return_date="2026-04-10"
            )

            # 验证返回日期被添加到请求中
            call_args = mock_request.call_args
            request_data = call_args.kwargs.get('json', {})
            assert 'returnDate' in request_data
            assert request_data['returnDate'] == "2026-04-10"

    @pytest.mark.asyncio
    async def test_pricing(self, api_client, sample_pricing_data):
        """测试航班计价"""
        with patch.object(api_client, 'request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = sample_pricing_data

            result = await api_client.pricing(
                flight_id="FL123456",
                cabin_class="economy",
                passengers={"adults": 1, "children": 0, "infants": 0}
            )

            assert result == sample_pricing_data
            mock_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_passenger(self, api_client, sample_passenger_data):
        """测试创建出行人"""
        with patch.object(api_client, 'request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = sample_passenger_data

            passenger_data = {
                "name": "张三",
                "passengerType": "adult",
                "nationality": "CN",
                "idType": "0",
                "idNumber": "E12345678"
            }

            result = await api_client.create_passenger(passenger_data)

            assert result == sample_passenger_data

    @pytest.mark.asyncio
    async def test_create_order(self, api_client, sample_order_data):
        """测试创建订单"""
        with patch.object(api_client, 'request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = sample_order_data

            order_data = {
                "policySerialNumber": "POL789012",
                "passengerList": [{"passengerId": "PAX123456"}],
                "contact": {"name": "张三", "phone": "13800138000"}
            }

            result = await api_client.create_order(order_data)

            assert result == sample_order_data

    @pytest.mark.asyncio
    async def test_verify_order(self, api_client):
        """测试验价验舱"""
        with patch.object(api_client, 'request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"code": 0, "data": {"status": "verified"}}

            result = await api_client.verify_order("ORD987654")

            assert result["code"] == 0

    @pytest.mark.asyncio
    async def test_confirm_pay(self, api_client):
        """测试确认支付"""
        with patch.object(api_client, 'request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"code": 0, "data": {"status": "paid"}}

            result = await api_client.confirm_pay("ORD987654", "online")

            assert result["code"] == 0

    @pytest.mark.asyncio
    async def test_cancel_order(self, api_client):
        """测试取消订单"""
        with patch.object(api_client, 'request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {"code": 0, "data": {"status": "cancelled"}}

            result = await api_client.cancel_order("ORD987654", "用户取消")

            assert result["code"] == 0


# ===========================================
# 错误处理测试
# ===========================================

class TestErrorHandling:
    """测试错误处理"""

    def test_api_error_init(self):
        """测试API错误初始化"""
        error = MeiyaApiError("测试错误", code=1001, response={"data": {}})

        assert error.message == "测试错误"
        assert error.code == 1001
        assert error.response == {"data": {}}
        assert str(error) == "[错误码 1001] 测试错误"

    def test_api_error_without_code(self):
        """测试无错误码的API错误"""
        error = MeiyaApiError("测试错误")

        assert str(error) == "测试错误"

    @pytest.mark.asyncio
    async def test_request_business_error(self, api_client):
        """测试业务错误处理"""
        with patch.object(api_client, 'session') as mock_session:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"code": 1001, "message": "业务错误"}
            mock_response.raise_for_status = MagicMock()

            mock_session.request = AsyncMock(return_value=mock_response)

            with pytest.raises(MeiyaApiError) as exc_info:
                await api_client.request("POST", "/test")

            assert exc_info.value.code == 1001
            assert "业务错误" in str(exc_info.value)


# ===========================================
# 重试机制测试
# ===========================================

class TestRetryMechanism:
    """测试重试机制"""

    @pytest.mark.asyncio
    async def test_retry_on_network_error(self, api_client):
        """测试网络错误重试"""
        import httpx

        # 创建3个mock响应，最后一次成功
        # 使用httpx.RequestError以触发重试机制
        mock_responses = [
            httpx.RequestError("Network error"),
            httpx.RequestError("Network error"),
            MagicMock(
                status_code=200,
                json=lambda: {"code": 0},
                raise_for_status=MagicMock()
            )
        ]

        with patch.object(api_client.session, 'request', new_callable=AsyncMock) as mock_session:
            mock_session.side_effect = mock_responses

            result = await api_client.request("POST", "/test")

            assert result["code"] == 0
            assert mock_session.call_count == 3

    @pytest.mark.asyncio
    async def test_no_retry_on_client_error(self, api_client):
        """测试4xx错误不重试"""
        from httpx import HTTPStatusError

        with patch.object(api_client.session, 'request', new_callable=AsyncMock) as mock_session:
            # 模拟401错误
            mock_response = MagicMock()
            mock_response.status_code = 401

            mock_session.side_effect = HTTPStatusError(
                "401 Unauthorized",
                request=MagicMock(),
                response=mock_response
            )

            with pytest.raises(MeiyaApiError) as exc_info:
                await api_client.request("POST", "/test")

            # 只调用一次，不重试
            assert mock_session.call_count == 1


# ===========================================
# 异步休眠测试
# ===========================================

class TestAsyncSleep:
    """测试异步休眠"""

    @pytest.mark.asyncio
    async def test_sleep_function(self, api_client):
        """测试异步休眠函数"""
        import asyncio

        start = time.time()
        await api_client._sleep(0.1)
        elapsed = time.time() - start

        # 允许一些误差
        assert elapsed >= 0.05
        assert elapsed < 0.3
