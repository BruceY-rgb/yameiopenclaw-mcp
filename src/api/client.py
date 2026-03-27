"""
腾云商旅 API 客户端

调用 https://sla.ontuotu.com 的 Java 后端接口，涵盖：
  - 开放接口（公司密钥鉴权）：创建用户账号
  - 认证接口：登录获取 Token
  - 航班接口（Token 鉴权）：国际机票查询、退改签规则、订单详情
  - 出行人接口（Token 鉴权）：创建/查询出行人
  - 订单接口（Token 鉴权）：国际机票下单

接口路径参考：FlightController.java（/api/flight/...）
"""

import logging
import base64
import hashlib
import httpx
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# 基础地址
# ─────────────────────────────────────────────
BASE_URL = "https://sla.ontuotu.com"

# ─────────────────────────────────────────────
# 开放接口（公司密钥鉴权）
# ─────────────────────────────────────────────
API_OPEN_CREATE_USER   = "/api/open/createUser"        # 创建用户账号

# ─────────────────────────────────────────────
# 认证接口
# ─────────────────────────────────────────────
API_AUTH_LOGIN         = "/api/auth/loginByPassword"   # 用户登录，返回 JWT token

# ─────────────────────────────────────────────
# 航班接口（Token 鉴权）
# ─────────────────────────────────────────────
# 国际机票
API_INTL_SEARCH        = "/api/flight/intlsearch"         # 4.1 国际机票航班查询
API_INTL_SEARCH_ASYNC  = "/api/flight/intlsearchasync"    # 4.1 国际机票航班异步查询
API_INTL_TICKET_RULE   = "/api/flight/queryIntlShoppingRule"  # 4.2 国际退改签条款
API_INTL_ORDER_DETAIL  = "/api/flight/intldetail"         # 4.6 国际机票订单详情查询
API_INTL_SAVE_ORDER    = "/api/flight/intlsaveOrder"      # 4.3 国际机票订单采购生单

# 国际改签
API_INTL_TC_SEARCH     = "/api/flight/intltcsearch"       # 5.1 国际改签航班查询
API_INTL_TC_DETAIL     = "/api/flight/intltcdetail"       # 5.6 国际改签订单详情

# 国际退票
API_INTL_TR_DETAIL     = "/api/flight/intltrdetail"       # 6.4 国际退票单详情

# 国内机票
API_DOM_SEARCH         = "/api/flight/searchFlights"      # 1.1 国内航班查询
API_DOM_SEARCH_ASYNC   = "/api/flight/IDomesticShoppingPublish"   # 1.1 国内异步发布
API_DOM_SEARCH_DATA    = "/api/flight/IGetDomesticShoppingData"   # 1.2 国内异步获取数据
API_DOM_TICKET_RULE    = "/api/flight/queryShoppingRule"  # 1.3 国内退改条款
API_DOM_ORDER_DETAIL   = "/api/flight/orderDetailQuery"   # 1.8 国内机票订单详情
API_DOM_TC_SEARCH      = "/api/flight/tcsearch"           # 2.1 国内改签航班查询
API_DOM_TC_DETAIL      = "/api/flight/tcdetail"           # 2.6 国内TC订单详情
API_DOM_TR_DETAIL      = "/api/flight/trdetail"           # 3.4 国内退票单详情

# 通知回调
API_NOTICE_TO          = "/api/flight/meiyaTONotice"      # 下单通知
API_NOTICE_TR          = "/api/flight/meiyaTRNotice"      # 退票单通知
API_NOTICE_TC          = "/api/flight/meiyaTCNotice"      # 改签单通知

# 机场数据
API_AIRPORT_PAGE       = "/api/flight/getAirportPage"     # 获取机票地址分页

# ─────────────────────────────────────────────
# 出行人接口（Token 鉴权）
# ─────────────────────────────────────────────
API_PASSENGER_SAVE     = "/api/passenger/save"            # 创建出行人
API_PASSENGER_LIST     = "/api/passenger/list"            # 出行人列表


class OntuotuApiClient:
    """腾云商旅 API 客户端

    支持两种鉴权模式：
    1. 公司密钥模式（AppKey + AppSecret）：用于开放接口，如创建用户
    2. Token 模式（Bearer Token）：用于业务接口，如查询航班、下单

    使用方式：
        client = OntuotuApiClient(app_key="xxx", app_secret="yyy")
        token = await client.login(username, password)
        client.set_token(token)
        result = await client.search_intl_flights(...)
    """

    def __init__(
        self,
        app_key: str = "",
        app_secret: str = "",
        base_url: str = BASE_URL,
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        self.app_key = app_key
        self.app_secret = app_secret
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self._token: Optional[str] = None

        self.session = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(timeout),
            follow_redirects=True,
        )

    # ─────────────────────────────────────────
    # Token 管理
    # ─────────────────────────────────────────

    def set_token(self, token: str):
        """设置当前用户 Token"""
        self._token = token

    def clear_token(self):
        """清除 Token"""
        self._token = None

    # ─────────────────────────────────────────
    # 底层 HTTP 请求
    # ─────────────────────────────────────────

    async def request(
        self,
        method: str,
        path: str,
        *,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        use_app_key: bool = False,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """发送 HTTP 请求

        Args:
            method: HTTP 方法（GET/POST）
            path: 接口路径（不含 base_url）
            json: 请求体（JSON）
            params: 查询参数
            use_app_key: True 时使用公司密钥鉴权，False 时使用 Token 鉴权
            extra_headers: 额外请求头

        Returns:
            响应 JSON 数据
        """
        headers: Dict[str, str] = {"Content-Type": "application/json"}

        if use_app_key:
            # 公司密钥鉴权
            headers["AppKey"] = self.app_key
            headers["AppSecret"] = self.app_secret
        elif self._token:
            # Token 鉴权（Bearer token）
            headers["Authorization"] = "Bearer " + self._token

        if extra_headers:
            headers.update(extra_headers)

        last_error: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.debug(f"[{method}] {path} (attempt {attempt})")
                response = await self.session.request(
                    method,
                    path,
                    json=json,
                    params=params,
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()
                logger.debug(f"响应: {str(data)[:200]}")
                return data
            except httpx.HTTPStatusError as e:
                logger.warning(f"HTTP 错误 {e.response.status_code}: {path}")
                last_error = e
                if e.response.status_code in (400, 401, 403, 404):
                    break  # 不重试客户端错误
            except (httpx.ConnectError, httpx.TimeoutException) as e:
                logger.warning(f"网络错误 (attempt {attempt}): {e}")
                last_error = e

        raise RuntimeError(f"请求失败 [{method} {path}]: {last_error}")

    # ─────────────────────────────────────────
    # 开放接口：创建用户账号（公司密钥鉴权）
    # ─────────────────────────────────────────

    async def create_user(
        self,
        real_name: Optional[str] = None,
        phone: Optional[str] = None,
        email: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """通过公司密钥调用开放接口，创建用户账号

        步骤 3：小龙虾使用公司账号密钥，调用开放接口，创建用户账号密码。

        签名算法（参考开放接口文档）：
        1. 参数按字母 a-z 排序
        2. 转成 JSON 字符串
        3. Base64 编码
        4. MD5 加密得到 hash 值

        请求参数：appKey + hash（不含 secret）

        注意：开放接口创建用户不需要传 username/password
        返回的是系统生成的用户名和密码

        Returns:
            创建结果，包含 username, password
        """
        # 生成签名 hash
        # 1. 参数按字母 a-z 排序，构造 JSON（无空格）
        json_str = '{"appKey":"' + self.app_key + '","secret":"' + self.app_secret + '"}'

        # 2. Base64 编码
        base64_str = base64.b64encode(json_str.encode('utf-8')).decode('utf-8')

        # 3. MD5 加密
        hash_value = hashlib.md5(base64_str.encode('utf-8')).hexdigest()

        # 请求体：appKey + hash（不含 secret）
        body: Dict[str, Any] = {
            "appKey": self.app_key,
            "hash": hash_value,
        }

        # 注意：开放接口创建用户不需要传 username/password
        # 返回的是系统生成的用户名和密码
        if extra:
            body.update(extra)

        return await self.request(
            "POST",
            API_OPEN_CREATE_USER,
            json=body,
        )

    # ─────────────────────────────────────────
    # 认证接口：登录获取 Token
    # ─────────────────────────────────────────

    async def login(
        self,
        username: str,
        password: str,
    ) -> str:
        """登录获取 JWT Token

        步骤 4：小龙虾使用用户账号密码，调用登录接口，得到 token。

        Args:
            username: 用户名
            password: 密码

        Returns:
            JWT token 字符串
        """
        body: Dict[str, Any] = {
            "username": username,
            "password": password,
        }
        resp = await self.request("POST", API_AUTH_LOGIN, json=body)

        # 响应结构：{"code":"000000","message":"成功","value":"<token>"}
        code_val = resp.get("code", "")
        if code_val != "000000":
            raise RuntimeError(
                f"登录失败: code={code_val}, message={resp.get('message')}"
            )

        token = resp.get("value") or resp.get("data", {}).get("token", "")
        if not token:
            raise RuntimeError(f"登录响应中未找到 token: {resp}")

        self._token = token
        logger.info(f"用户 [{username}] 登录成功，已缓存 Token")
        return token

    # ─────────────────────────────────────────
    # 国际机票接口（Token 鉴权）
    # ─────────────────────────────────────────

    async def search_intl_flights(self, body: Dict[str, Any]) -> Dict[str, Any]:
        """4.1 国际机票航班查询（Shopping）

        路径: POST /api/flight/intlsearch

        Args:
            body: 查询参数，参考 FlightInternalReq，常用字段：
                - tripType: 行程类型（1=单程 2=往返）
                - fromCity: 出发城市/机场代码
                - toCity: 目的地城市/机场代码
                - fromDate: 出发日期（yyyy-MM-dd）
                - returnDate: 返程日期（往返时必填）
                - adultCount: 成人数量
                - childCount: 儿童数量
                - infantCount: 婴儿数量
                - cabin: 舱位（Y=经济 C=商务 F=头等）
        """
        return await self.request("POST", API_INTL_SEARCH, json=body)

    async def search_intl_flights_async(self, body: Dict[str, Any]) -> Dict[str, Any]:
        """4.1 国际机票航班异步查询（ShoppingDataQuery）

        路径: POST /api/flight/intlsearchasync
        """
        return await self.request("POST", API_INTL_SEARCH_ASYNC, json=body)

    async def query_intl_ticket_rule(self, body: Dict[str, Any]) -> Dict[str, Any]:
        """4.2 国际机票退改签条款查询（TicketRuleQuery）

        路径: POST /api/flight/queryIntlShoppingRule
        """
        return await self.request("POST", API_INTL_TICKET_RULE, json=body)

    async def save_intl_order(self, body: Dict[str, Any]) -> Dict[str, Any]:
        """4.3 国际机票订单采购生单（TOOrderSave）

        路径: POST /api/flight/intlsaveOrder

        步骤 7：小龙虾使用 token，国际机票下单。

        Args:
            body: 下单参数，常用字段：
                - flightId: 航班 ID（来自 intlsearch 结果）
                - serialNumber: 序列号（来自 intlsearch 结果）
                - policySerialNumber: 策略序列号（来自计价结果）
                - passengerList: 出行人列表（含 passengerId 或完整出行人信息）
                - contactName: 联系人姓名
                - contactPhone: 联系人电话
                - contactEmail: 联系人邮箱
        """
        return await self.request("POST", API_INTL_SAVE_ORDER, json=body)

    async def query_intl_order_detail(self, body: Dict[str, Any]) -> Dict[str, Any]:
        """4.6 国际机票订单详情查询（TOOrderDetailQuery）

        路径: POST /api/flight/intldetail
        """
        return await self.request("POST", API_INTL_ORDER_DETAIL, json=body)

    async def search_intl_tc_flights(self, body: Dict[str, Any]) -> Dict[str, Any]:
        """5.1 国际改签航班查询（TCShoppingInternal）

        路径: POST /api/flight/intltcsearch

        Args:
            body: 查询参数，参考 FlightTCShoppingInternalReq
        """
        return await self.request("POST", API_INTL_TC_SEARCH, json=body)

    async def query_intl_tc_order_detail(self, body: Dict[str, Any]) -> Dict[str, Any]:
        """5.6 国际改签订单详情（TCOrderDetailQueryInternal）

        路径: POST /api/flight/intltcdetail
        """
        return await self.request("POST", API_INTL_TC_DETAIL, json=body)

    async def query_intl_tr_order_detail(self, body: Dict[str, Any]) -> Dict[str, Any]:
        """6.4 国际退票单详情（TROrderDetailQueryInternal）

        路径: POST /api/flight/intltrdetail
        """
        return await self.request("POST", API_INTL_TR_DETAIL, json=body)

    # ─────────────────────────────────────────
    # 国内机票接口（Token 鉴权）
    # ─────────────────────────────────────────

    async def search_dom_flights(self, body: Dict[str, Any]) -> Dict[str, Any]:
        """1.1 国内航班查询

        路径: POST /api/flight/searchFlights
        """
        return await self.request("POST", API_DOM_SEARCH, json=body)

    async def search_dom_flights_async_publish(self, body: Dict[str, Any]) -> Dict[str, Any]:
        """1.1 国内航班异步查询（发布）

        路径: POST /api/flight/IDomesticShoppingPublish
        """
        return await self.request("POST", API_DOM_SEARCH_ASYNC, json=body)

    async def search_dom_flights_async_data(self, body: Dict[str, Any]) -> Dict[str, Any]:
        """1.2 国内航班异步查询（获取数据）

        路径: POST /api/flight/IGetDomesticShoppingData
        """
        return await self.request("POST", API_DOM_SEARCH_DATA, json=body)

    async def query_dom_ticket_rule(self, body: Dict[str, Any]) -> Dict[str, Any]:
        """1.3 国内退改条款查询

        路径: POST /api/flight/queryShoppingRule
        """
        return await self.request("POST", API_DOM_TICKET_RULE, json=body)

    async def query_dom_order_detail(self, body: Dict[str, Any]) -> Dict[str, Any]:
        """1.8 国内机票订单详情查询

        路径: POST /api/flight/orderDetailQuery
        """
        return await self.request("POST", API_DOM_ORDER_DETAIL, json=body)

    async def search_dom_tc_flights(self, body: Dict[str, Any]) -> Dict[str, Any]:
        """2.1 国内改签航班查询

        路径: POST /api/flight/tcsearch
        """
        return await self.request("POST", API_DOM_TC_SEARCH, json=body)

    async def query_dom_tc_order_detail(self, body: Dict[str, Any]) -> Dict[str, Any]:
        """2.6 国内TC订单详情查询

        路径: POST /api/flight/tcdetail
        """
        return await self.request("POST", API_DOM_TC_DETAIL, json=body)

    async def query_dom_tr_order_detail(self, body: Dict[str, Any]) -> Dict[str, Any]:
        """3.4 国内退票单详情

        路径: POST /api/flight/trdetail
        """
        return await self.request("POST", API_DOM_TR_DETAIL, json=body)

    # ─────────────────────────────────────────
    # 出行人接口（Token 鉴权）
    # ─────────────────────────────────────────

    async def save_passenger(self, body: Dict[str, Any]) -> Dict[str, Any]:
        """创建出行人

        路径: POST /api/passenger/save

        步骤 6：小龙虾使用 token，创建出行人。

        Args:
            body: 出行人信息，常用字段：
                - name: 姓名
                - passengerType: 乘客类型（0=成人 1=儿童 2=婴儿）
                - nationality: 国籍二字码
                - idType: 证件类型（0=护照 等）
                - idNumber: 证件号码
                - idExpiration: 证件有效期（yyyy-MM-dd）
                - gender: 性别（1=男 0=女）
                - birthday: 出生日期（yyyy-MM-dd）
                - phone: 手机号（可选）
                - email: 邮箱（可选）
        """
        return await self.request("POST", API_PASSENGER_SAVE, json=body)

    async def list_passengers(self, body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """查询出行人列表

        路径: POST /api/passenger/list
        """
        return await self.request("POST", API_PASSENGER_LIST, json=body or {})

    # ─────────────────────────────────────────
    # 机场数据接口
    # ─────────────────────────────────────────

    async def get_airport_page(self, page_num: int = 1, page_size: int = 20) -> Dict[str, Any]:
        """获取机场/城市数据分页

        路径: POST /api/flight/getAirportPage
        """
        return await self.request(
            "POST",
            API_AIRPORT_PAGE,
            json={"pageNum": page_num, "pageSize": page_size},
        )

    # ─────────────────────────────────────────
    # 生命周期
    # ─────────────────────────────────────────

    async def close(self):
        """关闭 HTTP 客户端"""
        await self.session.aclose()
        logger.info("API 客户端已关闭")


# 向后兼容别名（旧代码引用 MeiyaApiClient 的地方不需要改动）
MeiyaApiClient = OntuotuApiClient
