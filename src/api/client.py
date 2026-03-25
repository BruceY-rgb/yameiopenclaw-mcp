"""
美亚航旅API客户端

提供对美亚航旅API的异步HTTP请求封装，支持Token认证、重试机制和错误处理。
接口路径参考: https://meiya.apifox.cn/
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

# ============================================================
# 接口路径常量（严格对应官方文档 meiya.apifox.cn）
# ============================================================

# 国际机票接口前缀
_INTL_TICKET = "/supplier/supplierapi/thgeneralinterface/SupplierIntlTicket/v2"
# 国际机票订单接口前缀（生单/验价/确认支付/查询/取消）
_INTL_ORDER = "/supplier/supplierapi/thgeneralinterface/SupplierIntlToOrder/v2"
# 国际国内机票公共接口前缀
_TICKET_COMMON = "/supplier/supplierapi/thgeneralinterface/SupplierTicketCommon/v2"

# 各接口完整路径
API_SHOPPING = f"{_INTL_TICKET}/Shopping"
API_SHOPPING_DATA_QUERY = f"{_INTL_TICKET}/ShoppingDataQuery"
API_SHOPPING_MORE_PRICE = f"{_INTL_TICKET}/ShoppingMorePrice"
API_TICKET_RULE_QUERY = f"{_INTL_TICKET}/TicketRuleQuery"
API_PRICING = f"{_INTL_TICKET}/Pricing"
API_PRICING_DATA_QUERY = f"{_INTL_TICKET}/PricingDataQuery"
API_STOPOVER_QUERY = f"{_INTL_TICKET}/StopoverQuery"
API_SHOPPING_FLIGHT = f"{_INTL_TICKET}/ShoppingFlight"
API_ORDER_SAVE = f"{_INTL_ORDER}/TOOrderSave"
API_ORDER_PAY_VER = f"{_INTL_ORDER}/OrderPayVer"
API_ORDER_PAY_CONFIRM = f"{_INTL_ORDER}/OrderPayConfirm"
API_ORDER_DETAIL_QUERY = f"{_INTL_ORDER}/TOOrderDetailQuery"
API_ORDER_CANCEL = f"{_INTL_ORDER}/TOOrderCancel"
API_VOYAGE_CHANGE = f"{_TICKET_COMMON}/VoyageChangeLibraryQuery"


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

    Token 签名算法（参考官方文档 meiya.apifox.cn 概述页）：
      1. 获取当前时间戳（毫秒）
      2. 将请求体序列化为 JSON 字符串
      3. 拼接明文: username + pwd + timestamp + body_json
      4. MD5 加密（取原始字节）
      5. Base64 编码
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
            username: API用户名（签约后获取）
            password: API密码（签约后获取，需保密）
            timeout: 请求超时时间（秒）
            max_retries: 最大重试次数
        """
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self.timeout = timeout
        self.max_retries = max_retries

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

        算法（参考官方文档 meiya.apifox.cn 概述页 JS 示例）:
          mingwen = username + pwd + timestamp + JSON.stringify(body)
          tokenArr = CryptoJS.MD5(CryptoJS.enc.Utf8.parse(mingwen))
          token = CryptoJS.enc.Base64.stringify(tokenArr)

        Args:
            body: 请求体数据

        Returns:
            包含 UserName / TimeStamp / Token / Content-Type 的 Header 字典
        """
        timestamp = str(int(time.time() * 1000))

        if body:
            body_str = json.dumps(body, ensure_ascii=False, separators=(',', ':'))
        else:
            body_str = ""

        mingwen = f"{self.username}{self.password}{timestamp}{body_str}"
        md5_hash = hashlib.md5(mingwen.encode('utf-8')).digest()
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
        auth_headers = self._generate_auth_headers(kwargs.get('json', {}))
        request_headers = {**auth_headers, **(headers or {})}

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

                response.raise_for_status()
                data = response.json()

                if not self._is_success(data):
                    error_msg = data.get("description") or data.get("message") or data.get("msg") or "未知错误"
                    error_code = data.get("code", -1)
                    raise MeiyaApiError(error_msg, code=error_code, response=data)

                logger.debug(f"请求成功: {method} {url}")
                return data

            except httpx.HTTPStatusError as e:
                last_error = e
                logger.warning(f"HTTP错误: {e.response.status_code}, 尝试 {attempt + 1}")
                if 400 <= e.response.status_code < 500:
                    raise MeiyaApiError(f"HTTP错误: {e.response.status_code}")

            except httpx.RequestError as e:
                last_error = e
                logger.warning(f"请求错误: {e}, 尝试 {attempt + 1}")

            except MeiyaApiError:
                raise

            except Exception as e:
                last_error = e
                logger.error(f"未知错误: {e}")
                raise

            if attempt < self.max_retries - 1:
                wait_time = 2 ** attempt
                logger.info(f"等待 {wait_time} 秒后重试...")
                await self._sleep(wait_time)

        raise MeiyaApiError(f"请求失败，已重试{self.max_retries}次: {last_error}")

    async def _sleep(self, seconds: float):
        """异步休眠"""
        import asyncio
        await asyncio.sleep(seconds)

    def _is_success(self, data: Dict[str, Any]) -> bool:
        """检查API响应是否成功

        官方文档说明：code 为 20000 表示成功，非 20000 表异常。
        """
        code = data.get("code")
        if code is not None:
            return str(code) == "20000" or code == 0
        if "success" in data:
            return data["success"] is True
        return True

    # ===========================================
    # 国际机票接口封装（路径严格对应 meiya.apifox.cn）
    # ===========================================

    async def search_flights(
        self,
        dep_airport: str,
        arr_airport: str,
        dep_date: str,
        adults: int = 1,
        children: int = 0,
        infants: int = 0,
        cabin_types: Optional[List[str]] = None,
        trip_type: str = "1",
        is_direction: str = "0",
        is_async: bool = False,
        return_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """国际机票航班查询 (Shopping)

        文档路径: POST /supplier/supplierapi/thgeneralinterface/SupplierIntlTicket/v2/Shopping

        Args:
            dep_airport: 出发地机场代码（如 PEK）
            arr_airport: 目的地机场代码（如 JFK）
            dep_date: 出发日期（YYYY-MM-DD）
            adults: 成人数量
            children: 儿童数量
            infants: 婴儿数量
            cabin_types: 舱位等级列表，如 ["0"]（0=经济舱 1=豪华经济舱 3=商务舱 4=头等舱）
            trip_type: 行程类别（1=单程 2=往返 3=联程 4=缺口程）
            is_direction: 飞行偏好（0=不限 1=直飞 2=最大中转1次 3=最大中转2次）
            is_async: 是否异步查询
            return_date: 返程日期（往返时使用，格式 YYYY-MM-DD）

        Returns:
            航班查询结果，包含 detail.serialNumber 和 detail.flightDetailList
        """
        if cabin_types is None:
            cabin_types = ["0"]

        origin_destinations = [{
            "depAirport": dep_airport,
            "arrAirport": arr_airport,
            "depDate": dep_date,
            "cabinTypes": cabin_types
        }]

        # 往返时添加返程段
        if trip_type == "2" and return_date:
            origin_destinations.append({
                "depAirport": arr_airport,
                "arrAirport": dep_airport,
                "depDate": return_date,
                "cabinTypes": cabin_types
            })

        passengers = []
        if adults > 0:
            passengers.append({"passengerType": 0, "count": adults})
        if children > 0:
            passengers.append({"passengerType": 1, "count": children})
        if infants > 0:
            passengers.append({"passengerType": 2, "count": infants})

        request_data = {
            "isDirection": is_direction,
            "originDestinations": origin_destinations,
            "passengers": passengers,
            "tripType": trip_type,
            "isAsync": is_async,
            "isRetrunTransferBaggage_visas": False
        }

        return await self.request("POST", API_SHOPPING, json=request_data)

    async def get_shopping_data(self, serial_number: str) -> Dict[str, Any]:
        """获取异步查询结果 (ShoppingDataQuery)

        文档路径: POST /supplier/supplierapi/thgeneralinterface/SupplierIntlTicket/v2/ShoppingDataQuery

        Args:
            serial_number: Shopping 接口返回的 serialNumber

        Returns:
            异步查询结果
        """
        return await self.request(
            "POST",
            API_SHOPPING_DATA_QUERY,
            json={"serialNumber": serial_number}
        )

    async def get_flight_details(self, flight_id: str, serial_number: str) -> Dict[str, Any]:
        """获取航班明细 (ShoppingFlight)

        文档路径: POST /supplier/supplierapi/thgeneralinterface/SupplierIntlTicket/v2/ShoppingFlight

        Args:
            flight_id: 航班 ID（Shopping 接口返回的 flightID）
            serial_number: Shopping 接口返回的 serialNumber

        Returns:
            航班明细信息
        """
        return await self.request(
            "POST",
            API_SHOPPING_FLIGHT,
            json={"flightID": flight_id, "serialNumber": serial_number}
        )

    async def get_more_price(self, flight_id: str, serial_number: str) -> Dict[str, Any]:
        """获取更多价格（全舱位）(ShoppingMorePrice)

        文档路径: POST /supplier/supplierapi/thgeneralinterface/SupplierIntlTicket/v2/ShoppingMorePrice

        Args:
            flight_id: 航班 ID
            serial_number: Shopping 接口返回的 serialNumber

        Returns:
            全舱位价格列表
        """
        return await self.request(
            "POST",
            API_SHOPPING_MORE_PRICE,
            json={"flightID": flight_id, "serialNumber": serial_number}
        )

    async def query_ticket_rule(self, flight_id: str, serial_number: str) -> Dict[str, Any]:
        """查询退改签规则 (TicketRuleQuery)

        文档路径: POST /supplier/supplierapi/thgeneralinterface/SupplierIntlTicket/v2/TicketRuleQuery

        Args:
            flight_id: 航班 ID
            serial_number: Shopping 接口返回的 serialNumber

        Returns:
            退改签规则
        """
        return await self.request(
            "POST",
            API_TICKET_RULE_QUERY,
            json={"flightID": flight_id, "serialNumber": serial_number}
        )

    async def pricing(
        self,
        flight_id: str,
        serial_number: str,
        airline: str,
        passengers: Optional[List[Dict[str, Any]]] = None,
        is_async: bool = False
    ) -> Dict[str, Any]:
        """国际机票计价 (Pricing) - 实时航班计价模式

        文档路径: POST /supplier/supplierapi/thgeneralinterface/SupplierIntlTicket/v2/Pricing

        计价模式说明：
          - 实时航班计价：需同时传 serialNumber 和 flightID（本方法默认使用此模式）
          - PNR 计价：传 PNR 字段（需另行调用）
          - 航段计价：传 flightList（需另行调用）

        Args:
            flight_id: 航班 ID（Shopping 接口返回的 flightID）
            serial_number: Shopping 接口返回的 serialNumber
            airline: 出票航司二字码
            passengers: 乘客类型列表，如 [{"passengerType": 0, "passengerCount": 1}]
            is_async: 是否异步计价

        Returns:
            计价结果，包含 detail[].serialNumber（即 policySerialNumber）
        """
        if passengers is None:
            passengers = [{"passengerType": 0, "passengerCount": 1}]

        request_data = {
            "airline": airline,
            "passengerTypeList": passengers,
            "serialNumber": serial_number,
            "flightID": flight_id,
            "isAsync": is_async
        }

        return await self.request("POST", API_PRICING, json=request_data)

    async def get_pricing_data(self, request_key: str) -> Dict[str, Any]:
        """获取异步计价结果 (PricingDataQuery)

        文档路径: POST /supplier/supplierapi/thgeneralinterface/SupplierIntlTicket/v2/PricingDataQuery

        Args:
            request_key: Pricing 接口异步模式返回的 requestKey

        Returns:
            计价结果
        """
        return await self.request(
            "POST",
            API_PRICING_DATA_QUERY,
            json={"requestKey": request_key}
        )

    async def query_stopover(self, flight_id: str, serial_number: str) -> Dict[str, Any]:
        """查询经停信息 (StopoverQuery)

        文档路径: POST /supplier/supplierapi/thgeneralinterface/SupplierIntlTicket/v2/StopoverQuery

        Args:
            flight_id: 航班 ID
            serial_number: Shopping 接口返回的 serialNumber

        Returns:
            经停信息
        """
        return await self.request(
            "POST",
            API_STOPOVER_QUERY,
            json={"flightID": flight_id, "serialNumber": serial_number}
        )

    async def create_order(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """国际机票订单采购生单 (TOOrderSave)

        文档路径: POST /supplier/supplierapi/thgeneralinterface/SupplierIntlToOrder/v2/TOOrderSave

        生单模式：
          - createOrderType=1：实时航班下单（需 policySerialNumber）
          - createOrderType=2：PNR 下单
          - createOrderType=3：航段导入下单

        Args:
            order_data: 订单数据，必须包含 policySerialNumber、createOrderType、passengerList、contact

        Returns:
            生单结果
        """
        return await self.request("POST", API_ORDER_SAVE, json=order_data)

    async def verify_order(self, order_id: str) -> Dict[str, Any]:
        """国际机票订单验价验舱 (OrderPayVer)

        文档路径: POST /supplier/supplierapi/thgeneralinterface/SupplierIntlToOrder/v2/OrderPayVer

        Args:
            order_id: 订单号

        Returns:
            验价验舱结果
        """
        return await self.request(
            "POST",
            API_ORDER_PAY_VER,
            json={"orderId": order_id}
        )

    async def confirm_pay(
        self,
        order_id: str,
        payment_method: str = "online"
    ) -> Dict[str, Any]:
        """国际机票订单确认支付 (OrderPayConfirm)

        文档路径: POST /supplier/supplierapi/thgeneralinterface/SupplierIntlToOrder/v2/OrderPayConfirm

        Args:
            order_id: 订单号
            payment_method: 支付方式（online/offline）

        Returns:
            支付结果
        """
        return await self.request(
            "POST",
            API_ORDER_PAY_CONFIRM,
            json={"orderId": order_id, "paymentMethod": payment_method}
        )

    async def query_order(self, order_id: str) -> Dict[str, Any]:
        """国际机票订单详情查询 (TOOrderDetailQuery)

        文档路径: POST /supplier/supplierapi/thgeneralinterface/SupplierIntlToOrder/v2/TOOrderDetailQuery

        Args:
            order_id: 订单号

        Returns:
            订单详情
        """
        return await self.request(
            "POST",
            API_ORDER_DETAIL_QUERY,
            json={"orderId": order_id}
        )

    async def cancel_order(
        self,
        order_id: str,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """国际机票订单取消 (TOOrderCancel)

        文档路径: POST /supplier/supplierapi/thgeneralinterface/SupplierIntlToOrder/v2/TOOrderCancel

        Args:
            order_id: 订单号
            reason: 取消原因

        Returns:
            取消结果
        """
        return await self.request(
            "POST",
            API_ORDER_CANCEL,
            json={"orderId": order_id, "reason": reason or "用户取消"}
        )

    async def get_flight_change(
        self,
        begin_date: str,
        end_date: str,
        order_id: Optional[str] = None,
        status: int = -1,
        page_index: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """查询航变信息 (VoyageChangeLibraryQuery)

        文档路径: POST /supplier/supplierapi/thgeneralinterface/SupplierTicketCommon/v2/VoyageChangeLibraryQuery

        Args:
            begin_date: 查询开始时间（yyyy-MM-dd）
            end_date: 查询结束时间（yyyy-MM-dd）
            order_id: TO 或 TC 订单号（可选）
            status: 航变状态（-1=所有 0=未查阅 1=已查阅）
            page_index: 页码（从 1 开始）
            page_size: 每页数量（最大 100）

        Returns:
            航变信息列表
        """
        request_data = {
            "beginDate": begin_date,
            "endDate": end_date,
            "status": status,
            "isAll": 0,
            "pageIndex": page_index,
            "pageSize": page_size
        }
        if order_id:
            request_data["orderId"] = order_id

        return await self.request("POST", API_VOYAGE_CHANGE, json=request_data)

    async def close(self):
        """关闭HTTP客户端"""
        await self.session.aclose()
        logger.info("API客户端已关闭")
