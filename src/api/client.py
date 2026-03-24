"""
美亚航旅API客户端

提供对美亚航旅API的异步HTTP请求封装，支持Token认证、重试机制和错误处理。
"""

import json
import time
import base64
import hashlib
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)


@dataclass
class ApiResponse:
    """API响应数据类"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    message: str = ""
    code: int = 0


class MeiyaApiError(Exception):
    """美亚航旅API错误"""

    def __init__(self, message: str, code: Optional[int] = None, response: Optional[Dict] = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.response = response

    def __str__(self):
        if self.code:
            return f"[错误码 {self.code}] {self.message}"
        return self.message


class MeiyaApiClient:
    """美亚航旅API客户端

    封装HTTP请求，处理底层通信，支持Token认证、重试机制和错误处理。
    """

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        timeout: float = 30.0,
        max_retries: int = 3
    ):
        """初始化API客户端

        Args:
            base_url: API基础URL
            username: API用户名
            password: API密码
            timeout: 请求超时时间（秒）
            max_retries: 最大重试次数
        """
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self.timeout = timeout
        self.max_retries = max_retries

        # 创建HTTP客户端
        self.session = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            headers={
                "Accept": "application/json",
                "User-Agent": "Meiya-MCP-Server/1.0"
            }
        )

        logger.info(f"API客户端初始化完成，base_url: {base_url}")

    def _generate_auth_headers(self, body: Dict[str, Any]) -> Dict[str, str]:
        """生成美亚航旅认证头

        算法:
        1. 获取当前时间戳（毫秒）
        2. 将请求体转为JSON字符串
        3. 拼接明文: username + pwd + timestamp + body
        4. MD5加密
        5. Base64编码

        Args:
            body: 请求体数据

        Returns:
            认证头字典
        """
        timestamp = str(int(time.time() * 1000))

        # 序列化请求体
        if body:
            body_str = json.dumps(body, ensure_ascii=False, separators=(',', ':'))
        else:
            body_str = ""

        # 拼接明文: username + pwd + timestamp + body
        mingwen = f"{self.username}{self.password}{timestamp}{body_str}"

        # MD5加密
        md5_hash = hashlib.md5(mingwen.encode('utf-8')).digest()

        # Base64编码
        token = base64.b64encode(md5_hash).decode('utf-8')

        logger.debug(f"生成Token: username={self.username}, timestamp={timestamp}")

        return {
            "UserName": self.username,
            "TimeStamp": timestamp,
            "Token": token,
            "Content-Type": "application/json"
        }

    async def request(
        self,
        method: str,
        endpoint: str,
        headers: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """发送HTTP请求

        Args:
            method: HTTP方法
            endpoint: API端点（相对路径）
            headers: 额外请求头
            **kwargs: 其他参数（如json、params等）

        Returns:
            API响应数据

        Raises:
            MeiyaApiError: API调用失败
        """
        url = f"{self.base_url}{endpoint}"

        # 生成认证头
        auth_headers = self._generate_auth_headers(kwargs.get('json', {}))

        # 合并请求头
        request_headers = {**auth_headers, **(headers or {})}

        # 重试机制
        last_error = None
        for attempt in range(self.max_retries):
            try:
                logger.debug(f"发送请求: {method} {url}, 尝试 {attempt + 1}/{self.max_retries}")

                response = await self.session.request(
                    method=method,
                    url=url,
                    headers=request_headers,
                    **kwargs
                )

                # 检查HTTP错误
                response.raise_for_status()

                # 解析响应
                data = response.json()

                # 检查业务错误
                if not self._is_success(data):
                    error_msg = data.get("message") or data.get("msg") or "未知错误"
                    error_code = data.get("code", -1)
                    raise MeiyaApiError(error_msg, code=error_code, response=data)

                logger.debug(f"请求成功: {method} {url}")
                return data

            except httpx.HTTPStatusError as e:
                last_error = e
                logger.warning(f"HTTP错误: {e.response.status_code}, 尝试 {attempt + 1}")

                # 如果是4xx错误，不重试
                if 400 <= e.response.status_code < 500:
                    raise MeiyaApiError(f"HTTP错误: {e.response.status_code}")

            except httpx.RequestError as e:
                last_error = e
                logger.warning(f"请求错误: {e}, 尝试 {attempt + 1}")

            except MeiyaApiError:
                # 业务错误不重试
                raise

            except Exception as e:
                last_error = e
                logger.error(f"未知错误: {e}")
                raise

            # 指数退避
            if attempt < self.max_retries - 1:
                wait_time = 2 ** attempt
                logger.info(f"等待 {wait_time} 秒后重试...")
                await self._sleep(wait_time)

        # 所有重试失败
        raise MeiyaApiError(f"请求失败，已重试{self.max_retries}次: {last_error}")

    async def _sleep(self, seconds: float):
        """异步休眠"""
        import asyncio
        await asyncio.sleep(seconds)

    def _is_success(self, data: Dict[str, Any]) -> bool:
        """检查API响应是否成功"""
        # 根据美亚航旅API的实际响应格式调整
        if "code" in data:
            return data["code"] == 0
        if "success" in data:
            return data["success"] is True
        return True

    # ===========================================
    # API接口封装
    # ===========================================

    async def search_flights(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        adults: int = 1,
        children: int = 0,
        infants: int = 0,
        cabin_class: str = "economy",
        trip_type: str = "one_way",
        return_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """查询国际航班

        Args:
            origin: 出发地机场代码（如PEK）
            destination: 目的地机场代码（如JFK）
            departure_date: 出发日期（YYYY-MM-DD）
            adults: 成人数量
            children: 儿童数量
            infants: 婴儿数量
            cabin_class: 舱位等级（economy/business/first）
            trip_type: 行程类型（one_way/round_trip）
            return_date: 返程日期（往返时必填）

        Returns:
            航班查询结果
        """
        request_data = {
            "origin": origin,
            "destination": destination,
            "departureDate": departure_date,
            "adults": adults,
            "children": children,
            "infants": infants,
            "cabinClass": cabin_class,
            "tripType": trip_type
        }

        if trip_type == "round_trip" and return_date:
            request_data["returnDate"] = return_date

        return await self.request(
            "POST",
            "/supplier/supplierapi/thgeneralinterface/SupplierIntlToSearch/v2/Shopping",
            json=request_data
        )

    async def get_shopping_data(self, search_id: str) -> Dict[str, Any]:
        """获取异步查询结果

        Args:
            search_id: 搜索ID

        Returns:
            查询结果
        """
        return await self.request(
            "POST",
            "/supplier/supplierapi/thgeneralinterface/SupplierIntlToSearch/v2/ShoppingDataQuery",
            json={"searchId": search_id}
        )

    async def get_flight_details(self, flight_id: str) -> Dict[str, Any]:
        """获取航班详情

        Args:
            flight_id: 航班ID

        Returns:
            航班详情
        """
        return await self.request(
            "POST",
            "/supplier/supplierapi/thgeneralinterface/SupplierIntlToSearch/v2/ShoppingFlight",
            json={"flightId": flight_id}
        )

    async def get_more_price(self, flight_id: str, cabin_class: str = "economy") -> Dict[str, Any]:
        """获取更多价格（全舱位）

        Args:
            flight_id: 航班ID
            cabin_class: 舱位等级

        Returns:
            价格列表
        """
        return await self.request(
            "POST",
            "/supplier/supplierapi/thgeneralinterface/SupplierIntlToSearch/v2/ShoppingMorePrice",
            json={
                "flightId": flight_id,
                "cabinClass": cabin_class
            }
        )

    async def query_ticket_rule(self, flight_id: str, cabin_class: str = "economy") -> Dict[str, Any]:
        """查询退改签规则

        Args:
            flight_id: 航班ID
            cabin_class: 舱位等级

        Returns:
            退改签规则
        """
        return await self.request(
            "POST",
            "/supplier/supplierapi/thgeneralinterface/SupplierIntlToSearch/v2/TicketRuleQuery",
            json={
                "flightId": flight_id,
                "cabinClass": cabin_class
            }
        )

    async def pricing(
        self,
        flight_id: str,
        cabin_class: str = "economy",
        passengers: Optional[Dict[str, int]] = None
    ) -> Dict[str, Any]:
        """航班计价

        Args:
            flight_id: 航班ID
            cabin_class: 舱位等级
            passengers: 乘客数量 {"adults": 1, "children": 0, "infants": 0}

        Returns:
            计价结果
        """
        if passengers is None:
            passengers = {"adults": 1, "children": 0, "infants": 0}

        return await self.request(
            "POST",
            "/supplier/supplierapi/thgeneralinterface/SupplierIntlToPricing/v2/Pricing",
            json={
                "flightId": flight_id,
                "cabinClass": cabin_class,
                "passengers": passengers
            }
        )

    async def get_pricing_data(self, pricing_id: str) -> Dict[str, Any]:
        """获取异步计价结果

        Args:
            pricing_id: 计价ID

        Returns:
            计价结果
        """
        return await self.request(
            "POST",
            "/supplier/supplierapi/thgeneralinterface/SupplierIntlToPricing/v2/PricingDataQuery",
            json={"pricingId": pricing_id}
        )

    async def query_stopover(self, flight_id: str) -> Dict[str, Any]:
        """查询经停信息

        Args:
            flight_id: 航班ID

        Returns:
            经停信息
        """
        return await self.request(
            "POST",
            "/supplier/supplierapi/thgeneralinterface/SupplierIntlToSearch/v2/StopoverQuery",
            json={"flightId": flight_id}
        )

    async def create_passenger(self, passenger_data: Dict[str, Any]) -> Dict[str, Any]:
        """创建出行人

        Args:
            passenger_data: 出行人信息

        Returns:
            出行人创建结果
        """
        return await self.request(
            "POST",
            "/passenger/create",
            json=passenger_data
        )

    async def update_passenger(self, passenger_id: str, passenger_data: Dict[str, Any]) -> Dict[str, Any]:
        """更新出行人

        Args:
            passenger_id: 出行人ID
            passenger_data: 出行人信息

        Returns:
            出行人更新结果
        """
        passenger_data["passengerId"] = passenger_id
        return await self.request(
            "POST",
            "/passenger/update",
            json=passenger_data
        )

    async def get_passenger(self, passenger_id: str) -> Dict[str, Any]:
        """获取出行人信息

        Args:
            passenger_id: 出行人ID

        Returns:
            出行人信息
        """
        return await self.request(
            "POST",
            "/passenger/get",
            json={"passengerId": passenger_id}
        )

    async def create_order(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """创建订单（生单）

        Args:
            order_data: 订单数据

        Returns:
            订单创建结果
        """
        return await self.request(
            "POST",
            "/supplier/supplierapi/thgeneralinterface/SupplierIntlToOrder/v2/TOOrderSave",
            json=order_data
        )

    async def verify_order(self, order_id: str) -> Dict[str, Any]:
        """验价验舱

        Args:
            order_id: 订单ID

        Returns:
            验价验舱结果
        """
        return await self.request(
            "POST",
            "/supplier/supplierapi/thgeneralinterface/SupplierIntlToOrder/v2/OrderPayVer",
            json={"orderId": order_id}
        )

    async def confirm_pay(
        self,
        order_id: str,
        payment_method: str = "online"
    ) -> Dict[str, Any]:
        """确认支付

        Args:
            order_id: 订单ID
            payment_method: 支付方式（online/offline）

        Returns:
            支付结果
        """
        return await self.request(
            "POST",
            "/supplier/supplierapi/thgeneralinterface/SupplierIntlToOrder/v2/OrderPayConfirm",
            json={
                "orderId": order_id,
                "paymentMethod": payment_method
            }
        )

    async def query_order(self, order_id: str) -> Dict[str, Any]:
        """查询订单详情

        Args:
            order_id: 订单ID

        Returns:
            订单详情
        """
        return await self.request(
            "POST",
            "/supplier/supplierapi/thgeneralinterface/SupplierIntlToOrder/v2/TOOrderDetailQuery",
            json={"orderId": order_id}
        )

    async def cancel_order(
        self,
        order_id: str,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """取消订单

        Args:
            order_id: 订单ID
            reason: 取消原因

        Returns:
            取消结果
        """
        return await self.request(
            "POST",
            "/supplier/supplierapi/thgeneralinterface/SupplierIntlToOrder/v2/TOOrderCancel",
            json={
                "orderId": order_id,
                "reason": reason or "用户取消"
            }
        )

    async def get_flight_change(self) -> Dict[str, Any]:
        """查询航变信息

        Returns:
            航变信息列表
        """
        return await self.request(
            "POST",
            "/common/flightchange",
            json={}
        )

    async def close(self):
        """关闭HTTP客户端"""
        await self.session.aclose()
        logger.info("API客户端已关闭")
