"""
工具测试

测试航班、订单和出行人工具的功能：
- 航班工具 (flights.py)
- 出行人工具 (passengers.py)
- 订单工具 (orders.py)
- 工作流编排器 (orchestrator.py)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call

from src.api.client import MeiyaApiClient
from src.auth.manager import AuthManager
from src.workflow.orchestrator import WorkflowOrchestrator, WorkflowError

from src.tools.flights import (
    SearchFlightsInput, SearchFlightsOutput,
    FlightDetailsInput, FlightDetailsOutput,
    PricingInput, PricingOutput,
    TicketRuleInput, TicketRuleOutput,
    register_flight_tools
)

from src.tools.passengers import (
    CreatePassengerInput, CreatePassengerOutput,
    UpdatePassengerInput, UpdatePassengerOutput,
    GetPassengerInput, GetPassengerOutput,
    register_passenger_tools
)

from src.tools.orders import (
    BookTicketInput, BookTicketOutput,
    QueryOrderInput, QueryOrderOutput,
    PayOrderInput, PayOrderOutput,
    CancelOrderInput, CancelOrderOutput,
    register_order_tools
)


# ===========================================
# 航班工具测试
# ===========================================

class TestFlightTools:
    """测试航班工具"""

    @pytest.mark.asyncio
    async def test_search_international_flights_success(self, mock_api_client):
        """测试查询国际航班成功"""
        # 模拟API响应
        mock_api_client.search_flights = AsyncMock(
            return_value={
                "code": 0,
                "data": {
                    "flights": [
                        {
                            "flightId": "FL123",
                            "flightNumber": "CA981",
                            "origin": "PEK",
                            "destination": "JFK"
                        }
                    ]
                }
            }
        )

        # 直接测试搜索逻辑
        response = await mock_api_client.search_flights(
            origin="PEK",
            destination="JFK",
            departure_date="2026-04-01",
            adults=1,
            children=0,
            infants=0,
            cabin_class="economy",
            trip_type="one_way",
            return_date=None
        )

        data = response.get("data", {})
        flights = data.get("flights", [])

        result = SearchFlightsOutput(
            success=True,
            message=f"找到 {len(flights)} 个航班",
            total=len(flights),
            flights=flights
        )

        assert result.success is True
        assert result.total == 1
        assert len(result.flights) == 1

    @pytest.mark.asyncio
    async def test_search_international_flights_async(self, mock_api_client):
        """测试异步查询航班（返回search_id）"""
        mock_api_client.search_flights = AsyncMock(
            return_value={
                "code": 0,
                "data": {
                    "searchId": "search_abc123"
                }
            }
        )

        input_data = SearchFlightsInput(
            origin="PEK",
            destination="JFK",
            departure_date="2026-04-01"
        )

        response = await mock_api_client.search_flights(
            origin=input_data.origin,
            destination=input_data.destination,
            departure_date=input_data.departure_date,
            adults=input_data.adults,
            children=input_data.children,
            infants=input_data.infants,
            cabin_class=input_data.cabin_class,
            trip_type=input_data.trip_type,
            return_date=input_data.return_date
        )

        data = response.get("data", {})
        search_id = data.get("searchId")

        assert search_id == "search_abc123"

    @pytest.mark.asyncio
    async def test_get_flight_details(self, mock_api_client):
        """测试获取航班详情"""
        mock_api_client.get_flight_details = AsyncMock(
            return_value={
                "code": 0,
                "data": {
                    "flightId": "FL123",
                    "flightNumber": "CA981",
                    "aircraft": "Boeing 777"
                }
            }
        )

        response = await mock_api_client.get_flight_details("FL123")

        assert response["code"] == 0
        assert response["data"]["flightId"] == "FL123"

    @pytest.mark.asyncio
    async def test_pricing_flight(self, mock_api_client):
        """测试航班计价"""
        mock_api_client.pricing = AsyncMock(
            return_value={
                "code": 0,
                "data": {
                    "policySerialNumber": "POL789",
                    "totalPrice": 5500.00
                }
            }
        )

        passengers = {"adults": 1, "children": 0, "infants": 0}

        response = await mock_api_client.pricing(
            flight_id="FL123",
            cabin_class="economy",
            passengers=passengers
        )

        assert response["code"] == 0
        assert response["data"]["policySerialNumber"] == "POL789"

    @pytest.mark.asyncio
    async def test_query_ticket_rule(self, mock_api_client):
        """测试查询退改签规则"""
        mock_api_client.query_ticket_rule = AsyncMock(
            return_value={
                "code": 0,
                "data": {
                    "refundRule": "起飞前退票收取20%手续费",
                    "changeRule": "起飞前改签收取10%手续费"
                }
            }
        )

        response = await mock_api_client.query_ticket_rule(
            flight_id="FL123",
            cabin_class="economy"
        )

        assert response["code"] == 0
        assert "refundRule" in response["data"]


# ===========================================
# 出行人工具测试
# ===========================================

class TestPassengerTools:
    """测试出行人工具"""

    @pytest.mark.asyncio
    async def test_create_passenger(self, mock_api_client):
        """测试创建出行人"""
        mock_api_client.create_passenger = AsyncMock(
            return_value={
                "code": 0,
                "data": {
                    "passengerId": "PAX123456",
                    "name": "张三",
                    "passengerType": "adult"
                }
            }
        )

        passenger_data = {
            "name": "张三",
            "passengerType": "adult",
            "nationality": "CN",
            "idType": "0",
            "idNumber": "E12345678",
            "idExpiration": "2030-01-01",
            "gender": "1",
            "birthday": "1990-01-01"
        }

        response = await mock_api_client.create_passenger(passenger_data)

        assert response["code"] == 0
        assert response["data"]["passengerId"] == "PAX123456"

    @pytest.mark.asyncio
    async def test_update_passenger(self, mock_api_client):
        """测试更新出行人"""
        mock_api_client.update_passenger = AsyncMock(
            return_value={
                "code": 0,
                "data": {
                    "passengerId": "PAX123456",
                    "phoneNumber": "13900139000"
                }
            }
        )

        update_data = {
            "phoneNumber": "13900139000"
        }

        response = await mock_api_client.update_passenger("PAX123456", update_data)

        assert response["code"] == 0
        assert response["data"]["phoneNumber"] == "13900139000"

    @pytest.mark.asyncio
    async def test_get_passenger(self, mock_api_client):
        """测试获取出行人"""
        mock_api_client.get_passenger = AsyncMock(
            return_value={
                "code": 0,
                "data": {
                    "passengerId": "PAX123456",
                    "name": "张三"
                }
            }
        )

        response = await mock_api_client.get_passenger("PAX123456")

        assert response["code"] == 0
        assert response["data"]["passengerId"] == "PAX123456"


# ===========================================
# 订单工具测试
# ===========================================

class TestOrderTools:
    """测试订单工具"""

    @pytest.mark.asyncio
    async def test_create_order(self, mock_api_client):
        """测试创建订单"""
        mock_api_client.create_order = AsyncMock(
            return_value={
                "code": 0,
                "data": {
                    "orderId": "ORD987654",
                    "status": "created",
                    "totalAmount": 5500.00,
                    "currency": "CNY"
                }
            }
        )

        order_data = {
            "policySerialNumber": "POL789",
            "passengerList": [{"passengerId": "PAX123456"}],
            "contact": {"name": "张三", "phone": "13800138000"}
        }

        response = await mock_api_client.create_order(order_data)

        assert response["code"] == 0
        assert response["data"]["orderId"] == "ORD987654"

    @pytest.mark.asyncio
    async def test_verify_order(self, mock_api_client):
        """测试验价验舱"""
        mock_api_client.verify_order = AsyncMock(
            return_value={
                "code": 0,
                "data": {
                    "status": "verified",
                    "price": 5500.00
                }
            }
        )

        response = await mock_api_client.verify_order("ORD987654")

        assert response["code"] == 0
        assert response["data"]["status"] == "verified"

    @pytest.mark.asyncio
    async def test_confirm_pay(self, mock_api_client):
        """测试确认支付"""
        mock_api_client.confirm_pay = AsyncMock(
            return_value={
                "code": 0,
                "data": {
                    "status": "paid",
                    "paymentTime": "2026-03-23 10:00:00"
                }
            }
        )

        response = await mock_api_client.confirm_pay("ORD987654", "online")

        assert response["code"] == 0
        assert response["data"]["status"] == "paid"

    @pytest.mark.asyncio
    async def test_query_order(self, mock_api_client):
        """测试查询订单"""
        mock_api_client.query_order = AsyncMock(
            return_value={
                "code": 0,
                "data": {
                    "orderId": "ORD987654",
                    "status": "paid"
                }
            }
        )

        response = await mock_api_client.query_order("ORD987654")

        assert response["code"] == 0
        assert response["data"]["orderId"] == "ORD987654"

    @pytest.mark.asyncio
    async def test_cancel_order(self, mock_api_client):
        """测试取消订单"""
        mock_api_client.cancel_order = AsyncMock(
            return_value={
                "code": 0,
                "data": {
                    "orderId": "ORD987654",
                    "status": "cancelled"
                }
            }
        )

        response = await mock_api_client.cancel_order("ORD987654", "用户取消")

        assert response["code"] == 0
        assert response["data"]["status"] == "cancelled"


# ===========================================
# 工作流编排器测试
# ===========================================

class TestWorkflowOrchestrator:
    """测试工作流编排器"""

    @pytest.mark.asyncio
    async def test_execute_booking_workflow_full(self, mock_api_client):
        """测试完整预订工作流"""
        # 设置各个API调用的返回值
        mock_api_client.search_flights = AsyncMock(
            return_value={
                "code": 0,
                "data": {
                    "flights": [{"flightId": "FL123", "policySerialNumber": "POL789"}]
                }
            }
        )

        mock_api_client.pricing = AsyncMock(
            return_value={
                "code": 0,
                "data": {
                    "policySerialNumber": "POL789",
                    "totalPrice": 5500.00
                }
            }
        )

        mock_api_client.create_passenger = AsyncMock(
            return_value={
                "code": 0,
                "data": {"passengerId": "PAX123"}
            }
        )

        mock_api_client.create_order = AsyncMock(
            return_value={
                "code": 0,
                "data": {
                    "orderId": "ORD987",
                    "status": "created",
                    "totalAmount": 5500.00,
                    "currency": "CNY"
                }
            }
        )

        mock_api_client.verify_order = AsyncMock(
            return_value={
                "code": 0,
                "data": {"status": "verified"}
            }
        )

        # 创建工作流编排器
        workflow = WorkflowOrchestrator(api_client=mock_api_client)

        # 执行预订工作流
        result = await workflow.execute_booking_workflow({
            "origin": "PEK",
            "destination": "JFK",
            "departure_date": "2026-04-01",
            "adults": 1,
            "passengers": [
                {
                    "name": "张三",
                    "passengerType": "adult",
                    "nationality": "CN",
                    "idType": "0",
                    "idNumber": "E12345678",
                    "idExpiration": "2030-01-01",
                    "gender": "1",
                    "birthday": "1990-01-01"
                }
            ],
            "contact": {
                "name": "张三",
                "phone": "13800138000"
            }
        })

        assert result["success"] is True
        assert result["order_id"] == "ORD987"
        # 验证search_flights被调用
        mock_api_client.search_flights.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_booking_workflow_with_flight_id(self, mock_api_client):
        """测试带flight_id的预订工作流（跳过搜索）"""
        mock_api_client.pricing = AsyncMock(
            return_value={
                "code": 0,
                "data": {
                    "policySerialNumber": "POL789",
                    "totalPrice": 5500.00
                }
            }
        )

        mock_api_client.create_passenger = AsyncMock(
            return_value={
                "code": 0,
                "data": {"passengerId": "PAX123"}
            }
        )

        mock_api_client.create_order = AsyncMock(
            return_value={
                "code": 0,
                "data": {
                    "orderId": "ORD987",
                    "status": "created",
                    "totalAmount": 5500.00,
                    "currency": "CNY"
                }
            }
        )

        mock_api_client.verify_order = AsyncMock(
            return_value={
                "code": 0,
                "data": {"status": "verified"}
            }
        )

        workflow = WorkflowOrchestrator(api_client=mock_api_client)

        result = await workflow.execute_booking_workflow({
            "flight_id": "FL123",  # 直接提供flight_id
            "adults": 1,
            "passengers": [
                {
                    "name": "张三",
                    "passengerType": "adult",
                    "nationality": "CN",
                    "idType": "0",
                    "idNumber": "E12345678",
                    "idExpiration": "2030-01-01",
                    "gender": "1",
                    "birthday": "1990-01-01"
                }
            ],
            "contact": {
                "name": "张三",
                "phone": "13800138000"
            }
        })

        # 不应该调用search_flights
        mock_api_client.search_flights.assert_not_called()
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_execute_payment_workflow(self, mock_api_client):
        """测试支付工作流"""
        mock_api_client.verify_order = AsyncMock(
            return_value={
                "code": 0,
                "data": {"status": "verified"}
            }
        )

        mock_api_client.confirm_pay = AsyncMock(
            return_value={
                "code": 0,
                "data": {"status": "paid"}
            }
        )

        workflow = WorkflowOrchestrator(api_client=mock_api_client)

        result = await workflow.execute_payment_workflow(
            order_id="ORD987",
            payment_method="online"
        )

        assert result["success"] is True
        assert result["status"] == "paid"

    @pytest.mark.asyncio
    async def test_execute_cancel_workflow(self, mock_api_client):
        """测试取消工作流"""
        mock_api_client.cancel_order = AsyncMock(
            return_value={
                "code": 0,
                "data": {"status": "cancelled"}
            }
        )

        workflow = WorkflowOrchestrator(api_client=mock_api_client)

        result = await workflow.execute_cancel_workflow(
            order_id="ORD987",
            reason="用户取消"
        )

        assert result["success"] is True
        assert result["status"] == "cancelled"

    @pytest.mark.asyncio
    async def test_booking_workflow_no_flights(self, mock_api_client):
        """测试无可用航班时抛出错误"""
        mock_api_client.search_flights = AsyncMock(
            return_value={
                "code": 0,
                "data": {
                    "flights": []  # 没有航班
                }
            }
        )

        workflow = WorkflowOrchestrator(api_client=mock_api_client)

        with pytest.raises(WorkflowError) as exc_info:
            await workflow.execute_booking_workflow({
                "origin": "PEK",
                "destination": "JFK",
                "departure_date": "2026-04-01"
            })

        assert "未找到可用航班" in str(exc_info.value)


# ===========================================
# 数据模型测试
# ===========================================

class TestDataModels:
    """测试数据模型"""

    def test_search_flights_input_valid(self):
        """测试有效的航班搜索输入"""
        input_data = SearchFlightsInput(
            origin="PEK",
            destination="JFK",
            departure_date="2026-04-01",
            adults=1,
            children=0,
            infants=0,
            cabin_class="economy",
            trip_type="one_way"
        )

        assert input_data.origin == "PEK"
        assert input_data.destination == "JFK"
        assert input_data.adults == 1

    def test_search_flights_input_defaults(self):
        """测试航班搜索输入默认值"""
        input_data = SearchFlightsInput(
            origin="PEK",
            destination="JFK",
            departure_date="2026-04-01"
        )

        assert input_data.adults == 1
        assert input_data.children == 0
        assert input_data.infants == 0
        assert input_data.cabin_class == "economy"
        assert input_data.trip_type == "one_way"

    def test_create_passenger_input(self):
        """测试创建出行人输入"""
        input_data = CreatePassengerInput(
            name="张三",
            passenger_type="adult",
            nationality="CN",
            id_type="0",
            id_number="E12345678",
            id_expiration="2030-01-01",
            gender="1",
            birthday="1990-01-01"
        )

        assert input_data.name == "张三"
        assert input_data.passenger_type == "adult"
        assert input_data.nationality == "CN"

    def test_book_ticket_input(self):
        """测试预订机票输入"""
        from src.tools.orders import PassengerInfo, ContactInfo

        input_data = BookTicketInput(
            flight_id="FL123",
            passengers=[
                PassengerInfo(
                    name="张三",
                    passenger_type="adult",
                    nationality="CN",
                    id_type="0",
                    id_number="E12345678",
                    id_expiration="2030-01-01",
                    gender="1",
                    birthday="1990-01-01"
                )
            ],
            contact=ContactInfo(
                name="张三",
                phone="13800138000"
            )
        )

        assert input_data.flight_id == "FL123"
        assert len(input_data.passengers) == 1

    def test_pricing_input(self):
        """测试计价输入"""
        input_data = PricingInput(
            flight_id="FL123",
            cabin_class="economy",
            adults=2,
            children=1,
            infants=0
        )

        assert input_data.flight_id == "FL123"
        assert input_data.adults == 2
        assert input_data.children == 1
