"""
工作流编排器

按照 7 步业务流程编排各接口调用：
  1. 运营后台创建公司账号密钥（人工操作，不在此处）
  2. 小龙虾配置公司账号密钥（环境变量，不在此处）
  3. create_user_account()  — 使用公司密钥创建用户账号
  4. login_user()           — 使用用户账号密码登录，获取 Token
  5. search_intl_flights()  — 使用 Token 查询国际机票
  6. create_passenger()     — 使用 Token 创建出行人
  7. book_intl_flight()     — 使用 Token 国际机票下单
"""

import json
import logging
from typing import Any, Dict, List, Optional

from src.api.client import OntuotuApiClient
from src.auth.manager import AuthManager

logger = logging.getLogger(__name__)


class WorkflowOrchestrator:
    """工作流编排器"""

    def __init__(self, api_client: OntuotuApiClient, auth_manager: AuthManager):
        self.api_client = api_client
        self.auth_manager = auth_manager

    # ─────────────────────────────────────────
    # 步骤 3：创建用户账号（公司密钥鉴权）
    # ─────────────────────────────────────────

    async def create_user_account(
        self,
        username: str,
        password: str,
        real_name: Optional[str] = None,
        phone: Optional[str] = None,
        email: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """步骤 3：使用公司密钥，通过开放接口创建用户账号

        Args:
            username: 用户名（用于后续登录）
            password: 密码（用于后续登录）
            real_name: 真实姓名（可选）
            phone: 手机号（可选）
            email: 邮箱（可选）
            extra: 其他扩展字段

        Returns:
            {"success": bool, "message": str, "data": {...}}
        """
        logger.info(f"[步骤 3] 创建用户账号：{username}")
        try:
            # 注意：api_client.create_user() 不需要 username/password 参数
            # 系统会自动生成用户名和密码返回
            resp = await self.api_client.create_user(
                real_name=real_name,
                phone=phone,
                email=email,
                extra=extra,
            )
            return {
                "success": True,
                "message": "用户账号创建成功",
                "data": resp,
            }
        except Exception as e:
            logger.error(f"[步骤 3] 创建用户账号失败：{e}")
            return {"success": False, "message": str(e), "data": None}

    # ─────────────────────────────────────────
    # 步骤 4：登录获取 Token
    # ─────────────────────────────────────────

    async def login_user(
        self,
        username: str,
        password: str,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """步骤 4：使用用户账号密码登录，获取 Token，并注入到 api_client

        Args:
            username: 用户名
            password: 密码
            force_refresh: 强制重新登录

        Returns:
            {"success": bool, "message": str, "token": str}
        """
        logger.info(f"[步骤4] 用户登录: {username}")
        try:
            token = await self.auth_manager.get_token(
                username=username,
                password=password,
                force_refresh=force_refresh,
            )
            # 将 Token 注入到 api_client，后续所有请求自动携带
            self.api_client.set_token(token)
            return {
                "success": True,
                "message": "登录成功",
                "token": token,
            }
        except Exception as e:
            logger.error(f"[步骤4] 用户登录失败: {e}")
            return {"success": False, "message": str(e), "token": ""}

    # ─────────────────────────────────────────
    # 步骤 5：查询国际机票（两步流程）
    # ─────────────────────────────────────────

    async def search_intl_flights(
        self,
        from_city: str,
        to_city: str,
        from_date: str,
        trip_type: int = 1,
        adult_count: int = 1,
        child_count: int = 0,
        infant_count: int = 0,
        cabin: str = "Y",
        return_date: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """步骤 5：使用 Token 查询国际机票（两步流程）

        参考 confirmOrder.vue 的实现：
        1. 先调用 /api/flight/intlsearchasync 获取 serialNumber
        2. 再调用 /api/flight/intlsearch 获取航班列表

        Args:
            from_city: 出发城市/机场代码（如 PEK、PVG）
            to_city: 目的地城市/机场代码（如 JFK、LHR）
            from_date: 出发日期（yyyy-MM-dd）
            trip_type: 行程类型（1=单程 2=往返）
            adult_count: 成人数量
            child_count: 儿童数量
            infant_count: 婴儿数量
            cabin: 舱位（Y=经济 C=商务 F=头等）
            return_date: 返程日期（往返时必填）
            extra: 其他扩展参数

        Returns:
            {
                "success": bool,
                "message": str,
                "serialNumber": str,      # 航班查询序列号
                "cacheExpirTime": str,    # 缓存过期时间
                "searchParams": dict,     # 原始搜索参数（下单时需要）
                "flights": list           # 航班列表
            }
        """
        logger.info(f"[步骤5] 查询国际机票: {from_city} -> {to_city}, {from_date}")

        # 舱位映射：Y=0 经济, C=3 商务, F=4 头等
        cabin_map = {"Y": "0", "C": "3", "F": "4"}
        cabin_type = cabin_map.get(cabin, "0")

        # 构建乘客列表
        passengers = []
        if adult_count > 0:
            passengers.append({"passengerType": 0, "count": adult_count, "passengerCount": adult_count})  # 0=成人
        if child_count > 0:
            passengers.append({"passengerType": 1, "count": child_count, "passengerCount": child_count})  # 1=儿童
        if infant_count > 0:
            passengers.append({"passengerType": 2, "count": infant_count, "passengerCount": infant_count})  # 2=婴儿

        # 飞行偏好映射
        direction_map = {1: "0", 2: "1"}  # 单程=不限, 往返=直飞(简化处理)
        is_direction = direction_map.get(trip_type, "0")

        # 构建搜索参数（参考开放接口文档）
        # 重要：depAirport/arrAirport 是二选一，不能为空
        search_params = {
            "isDirection": int(is_direction),
            "isAsync": True,
            "originDestinations": [
                {
                    "depAirport": from_city,  # 使用机场码
                    "depDate": from_date,
                    "arrAirport": to_city,     # 使用机场码
                }
            ],
            "passengers": passengers,
            "cabinTypes": [cabin_type],
        }

        # 往返航程需要添加返程信息
        if trip_type == 2 and return_date:
            search_params["originDestinations"].append({
                "depAirport": to_city,
                "depDate": return_date,
                "arrAirport": from_city,
            })

        if extra:
            search_params.update(extra)

        try:
            # 步骤1：调用 /api/flight/intlsearch 获取 serialNumber
            logger.info(f"[步骤5] 调用航班查询接口, 参数: {json.dumps(search_params, ensure_ascii=False)}")
            async_resp = await self.api_client.search_intl_flights(search_params)
            logger.info(f"[步骤5] 航班查询响应: {async_resp}")

            if async_resp.get("code") != "000000":
                error_msg = async_resp.get("description", async_resp.get("message", "查询失败"))
                logger.error(f"[步骤5] 查询失败: {error_msg}")
                return {
                    "success": False,
                    "message": f"查询失败: {error_msg}",
                    "serialNumber": "",
                    "flights": [],
                    "data": async_resp,
                }

            # 获取 serialNumber
            serial_number = async_resp.get("detail", {}).get("serialNumber", "")

            # 步骤2：调用 /api/flight/intlsearchasync 获取航班列表
            import asyncio
            await asyncio.sleep(3)  # 等待数据加载

            list_params = {
                "serialNumber": serial_number,
                "pageIndex": 1,
                "pageSize": 50,
            }
            list_resp = await self.api_client.search_intl_flights_async(list_params)
            logger.info(f"[步骤5] 获取航班列表响应: {str(list_resp)[:500]}")

            # 提取航班数据
            flights = []
            cache_expir_time = ""

            if list_resp.get("code") == "000000":
                detail = list_resp.get("detail", {})
                cache_expir_time = detail.get("cacheExpirTime", "")
                flights = detail.get("flightDetailList", [])
                total = list_resp.get("total", 0)

                logger.info(f"[步骤5] 查询成功: {total} 个航班, serialNumber={serial_number}")
                return {
                    "success": True,
                    "message": f"查询成功，共 {total} 个航班",
                    "serialNumber": serial_number,
                    "cacheExpirTime": cache_expir_time,
                    "searchParams": search_params,  # 原始搜索参数，下单时需要
                    "flights": flights,
                    "total": total,
                    "data": list_resp,
                }
            else:
                error_msg = list_resp.get("description", list_resp.get("message", "查询失败"))
                logger.error(f"[步骤5] 获取航班列表失败: {error_msg}")
                return {
                    "success": False,
                    "message": f"获取航班列表失败: {error_msg}",
                    "serialNumber": serial_number,
                    "flights": [],
                    "data": list_resp,
                }

        except Exception as e:
            logger.error(f"[步骤5] 查询国际机票失败: {e}")
            import traceback
            traceback.print_exc()
            return {"success": False, "message": str(e), "serialNumber": "", "flights": [], "data": None}

    # ─────────────────────────────────────────
    # 步骤 6：创建出行人
    # ─────────────────────────────────────────

    async def create_passenger(
        self,
        name: str,
        passenger_type: int,
        nationality: str,
        id_type: str,
        id_number: str,
        id_expiration: str,
        gender: int,
        birthday: str,
        phone: Optional[str] = None,
        email: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """步骤 6：使用 Token 创建出行人

        Args:
            name: 姓名
            passenger_type: 乘客类型（0=成人 1=儿童 2=婴儿）
            nationality: 国籍二字码（如 CN、US）
            id_type: 证件类型（0=护照 1=其他 3=港澳通行证 等）
            id_number: 证件号码
            id_expiration: 证件有效期（yyyy-MM-dd）
            gender: 性别（1=男 0=女）
            birthday: 出生日期（yyyy-MM-dd）
            phone: 手机号（可选）
            email: 邮箱（可选）
            extra: 其他扩展字段

        Returns:
            {"success": bool, "message": str, "passenger_id": str, "data": {...}}
        """
        logger.info(f"[步骤6] 创建出行人: {name}")
        # API 需要的字段名
        body: Dict[str, Any] = {
            "realName": name,
            "type": passenger_type,
            "nationality": nationality,
            "idType": id_type,
            "idCard": id_number,
            "idExpiration": id_expiration,
            "gender": gender,
            "birthday": birthday,
        }
        if phone:
            body["phone"] = phone
        if email:
            body["email"] = email
        if extra:
            body.update(extra)

        try:
            resp = await self.api_client.save_passenger(body)
            # 响应结构：{"code":"000000","value":{...}} 或 {"data":{...}}
            # API 创建成功时不返回 ID，需要查询列表获取
            code = resp.get("code", "")
            if code != "000000":
                raise RuntimeError(f"创建出行人失败: {resp.get('message', '未知错误')}")

            # 创建成功后，查询列表获取最新创建的出行人ID
            list_resp = await self.api_client.list_passengers()
            passengers = list_resp.get("value", [])
            # 按 ID 降序排列，取最新的
            if passengers:
                latest = max(passengers, key=lambda x: x.get("id", 0))
                passenger_id = str(latest.get("id", ""))
            else:
                passenger_id = ""

            logger.info(f"[步骤6] 创建出行人成功: passenger_id={passenger_id}")
            return {
                "success": True,
                "message": "出行人创建成功",
                "passenger_id": passenger_id,
                "data": resp,
            }
        except Exception as e:
            logger.error(f"[步骤6] 创建出行人失败: {e}")
            return {
                "success": False,
                "message": str(e),
                "passenger_id": "",
                "data": None,
            }

    # ─────────────────────────────────────────
    # 步骤 7：国际机票下单
    # ─────────────────────────────────────────

    async def book_intl_flight(
        self,
        flight_id: str,
        serial_number: str,
        passenger_ids: List[str],
        contact_name: str,
        contact_phone: str,
        contact_email: Optional[str] = None,
        policy_serial_number: Optional[str] = None,
        # 以下参数为新接口必需
        flight_data: Optional[Dict[str, Any]] = None,
        search_params: Optional[Dict[str, Any]] = None,
        passenger_infos: Optional[List[Dict[str, Any]]] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """步骤 7：使用 Token 国际机票下单

        调用 /api/order/createWechatPayOrder 接口

        参考 confirmOrder.vue 的参数构建：
        - policySerialNumber: 航班查询返回的 serialNumber
        - cacheExpirTime: 航班查询返回的缓存过期时间
        - flightSearchParam: 原始搜索参数（JSON 字符串）
        - cabinFareId: 舱位票价 ID
        - flightId: 航班 ID

        Args:
            flight_id: 航班 ID（来自 intlsearch 结果）
            serial_number: 序列号（来自 intlsearch 结果的 detail.serialNumber）
            passenger_ids: 出行人 ID 列表
            contact_name: 联系人姓名
            contact_phone: 联系人电话
            contact_email: 联系人邮箱（可选）
            policy_serial_number: 策略序列号（serialNumber）
            flight_data: 完整航班数据（来自查询结果）
            search_params: 航班查询参数（原始搜索参数，用于 flightSearchParam）
            passenger_infos: 出行人详细信息列表
            extra: 其他扩展字段

        Returns:
            {"success": bool, "message": str, "order_id": str, "data": {...}}
        """
        logger.info(
            f"[步骤7] 国际机票下单: flight_id={flight_id}, "
            f"passengers={passenger_ids}"
        )

        # 构建订单请求体
        # 参考: confirmOrder.vue 的 getParams() 方法
        body: Dict[str, Any] = {}

        # 出行人信息（使用第一个出行人）
        if passenger_infos and len(passenger_infos) > 0:
            p = passenger_infos[0]
            body.update({
                "realName": p.get("realName", p.get("name", "")),
                "idType": str(p.get("idType", "0")),
                "idCard": p.get("idCard", p.get("idNumber", "")),
                "phone": p.get("phone", ""),
                "type": p.get("type", p.get("passengerType", 0)),
                "gender": p.get("gender", 1) or 1,
                "idExpiration": p.get("idExpiration", "2030-12-31"),
                "birthday": p.get("birthday", "1990-01-01"),
                "countryCode": p.get("countryCode", "CN"),
            })
        else:
            body.update({
                "realName": contact_name,
                "idType": "0",
                "idCard": "",
                "phone": contact_phone,
                "type": 0,
                "gender": 1,
                "idExpiration": "2030-12-31",
                "birthday": "1990-01-01",
                "countryCode": "CN",
            })

        # 从 flight_data 中提取关键信息
        cabin_fare_id = ""
        cache_expir_time = ""
        trip_list = []

        if flight_data:
            # 获取舱位票价 ID（从 financeDetail 中）
            finance_detail = flight_data.get("financeDetail", {})
            finance_list = finance_detail.get("financeList", [])
            if finance_list:
                cabin_fare_id = finance_list[0].get("cabinFareId", "")
                if not cabin_fare_id:
                    cabin_fare_id = finance_list[0].get("cabinFare", "")

            # 获取缓存过期时间
            cache_expir_time = flight_data.get("cacheExpirTime", "")

            # 获取航段信息
            trip_list = flight_data.get("tripList", [])
            if not trip_list:
                trip_list = flight_data.get("trips", [])

        # 航班信息
        if trip_list:
            first_trip = trip_list[0]
            flight_list = first_trip.get("flightList", [])
            if flight_list:
                first_seg = flight_list[0]
                last_seg = flight_list[-1]

                # 修正日期格式为 yyyy-MM-dd HH:mm:ss
                def fix_datetime(dt):
                    if not dt:
                        return "2026-03-29 12:00:00"
                    if len(dt) == 10:
                        return f"{dt} 12:00:00"
                    if len(dt) == 16:
                        return f"{dt}:00"
                    return dt

                finance = flight_data.get("financeDetail", {}).get("financeList", [{}])[0]

                # 航线信息
                from_airport = first_seg.get("departureCityName", "") or first_seg.get("departureAirportNameCN", "")
                to_airport = last_seg.get("destinationCityName", "") or last_seg.get("destinationAirportNameCN", "")
                airline_name = flight_data.get("airlineNameCN", flight_data.get("airline", ""))

                body.update({
                    "orderTravelDate": fix_datetime(first_seg.get("departureDateTime")),
                    "orderTravelEndDate": fix_datetime(last_seg.get("arrivalDateTime")),
                    "airline": flight_data.get("airline", ""),
                    "feature": json.dumps({**flight_data, "tripList": trip_list}),
                    "orderItemDTOList": [{
                        "count": 1,
                        "productName": f"{from_airport} - {to_airport}",
                        "price": finance.get("salePrice", "0"),
                        "payAmount": finance.get("saleTotal", finance.get("salePrice", "0")),
                        "originPrice": finance.get("salePrice", "0"),
                        "productSpec": f"{airline_name} {flight_data.get('airline', '')} {flight_data.get('flightNumber', '')}",
                        "productFeature": "{}",
                        "touristId": int(passenger_ids[0]) if passenger_ids else 0,
                    }],
                })

        # 关键参数：policySerialNumber、cacheExpirTime、flightSearchParam
        # 参考 confirmOrder.vue:
        # policySerialNumber: this.flightInfo.serialNumber
        # cacheExpirTime: this.flightInfo.cacheExpirTime
        # flightSearchParam: JSON.stringify(this.departParamsbefore)
        body.update({
            "orderType": 0,  # 机票订单
            "payType": 3,  # 企业余额支付
            "orderTouristList": [{"touristId": int(pid)} for pid in passenger_ids],
            "flightType": 1,  # 国际航班
            "policySerialNumber": serial_number,  # 航班查询返回的 serialNumber
            "createOrderType": 1,  # 实时航班
            "isConvert": 1,  # 改为 1（参考 Vue）
            "mainName": contact_name,
            "mainPhone": contact_phone,
            "flightId": flight_id,
            "cacheExpirTime": cache_expir_time,  # 缓存过期时间
            "flightSearchParam": json.dumps(search_params) if search_params else "{}",  # 原始搜索参数（修正参数名）
            "tenantId": 1,  # 租户 ID（参考 Vue）
            "cabinFareId": cabin_fare_id,  # 舱位票价 ID
            "type": 0,  # 参考 Vue
        })

        if contact_email:
            body["contactEmail"] = contact_email

        if extra:
            body.update(extra)

        logger.info(f"[步骤7] 下单请求体: {json.dumps(body, ensure_ascii=False, indent=2)}")

        try:
            resp = await self.api_client.save_intl_order(body)
            logger.info(f"[步骤7] 下单响应: {resp}")

            # API 响应格式：{"code":"000000","value":{...},"message":"成功"}
            code = resp.get("code", "")
            if code != "000000":
                raise RuntimeError(f"下单失败: code={code}, message={resp.get('message', '未知错误')}")

            # 获取订单信息
            value = resp.get("value", {})
            order_id = value.get("orderId", "") or value.get("appId", "")

            logger.info(f"[步骤7] 下单成功: order_id={order_id}")
            return {
                "success": True,
                "message": "下单成功",
                "order_id": order_id,
                "data": resp,
            }
        except Exception as e:
            logger.error(f"[步骤7] 下单失败: {e}")
            return {
                "success": False,
                "message": str(e),
                "order_id": "",
                "data": None,
            }

    # ─────────────────────────────────────────
    # 便捷方法：完整预订流程（步骤 4-7 串联）
    # ─────────────────────────────────────────

    async def execute_full_booking(
        self,
        username: str,
        password: str,
        search_params: Dict[str, Any],
        passenger_infos: List[Dict[str, Any]],
        contact: Dict[str, Any],
        flight_selection: Dict[str, Any],
    ) -> Dict[str, Any]:
        """完整预订流程：登录 → 查询航班 → 创建出行人 → 下单

        Args:
            username: 用户名
            password: 密码
            search_params: 航班查询参数（传入 search_intl_flights）
            passenger_infos: 出行人信息列表（每项传入 create_passenger）
            contact: 联系人信息 {name, phone, email}
            flight_selection: 选定的航班信息
                {
                    "flightId": str,           # 航班 ID
                    "serialNumber": str,       # serialNumber（来自 search_intl_flights 返回）
                    "flightData": dict,        # 完整航班数据（来自 search_intl_flights 返回）
                }

        Returns:
            {"success": bool, "message": str, "order_id": str, "data": {...}}
        """
        # 步骤 4：登录
        login_result = await self.login_user(username, password)
        if not login_result["success"]:
            return {"success": False, "message": f"登录失败: {login_result['message']}"}

        # 步骤 6：创建出行人
        passenger_ids = []
        for pax in passenger_infos:
            pax_result = await self.create_passenger(**pax)
            if not pax_result["success"]:
                return {
                    "success": False,
                    "message": f"创建出行人失败: {pax_result['message']}",
                }
            passenger_ids.append(pax_result["passenger_id"])

        # 步骤 7：下单
        # 从 flight_selection 中获取完整数据
        flight_data = flight_selection.get("flightData", {})
        search_params_from_selection = flight_selection.get("searchParams", search_params)

        return await self.book_intl_flight(
            flight_id=flight_selection["flightId"],
            serial_number=flight_selection["serialNumber"],
            passenger_ids=passenger_ids,
            contact_name=contact["name"],
            contact_phone=contact["phone"],
            contact_email=contact.get("email"),
            policy_serial_number=flight_selection.get("serialNumber"),
            flight_data=flight_data,
            search_params=search_params_from_selection,
            passenger_infos=passenger_infos,
        )

    # ─────────────────────────────────────────
    # 便捷方法：一键预订（登录 + 查询 + 创建出行人 + 下单）
    # ─────────────────────────────────────────

    async def quick_booking(
        self,
        username: str,
        password: str,
        from_city: str,
        to_city: str,
        from_date: str,
        passenger_infos: List[Dict[str, Any]],
        contact: Dict[str, Any],
        flight_index: int = 0,
        trip_type: int = 1,
        cabin: str = "Y",
        return_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """一键预订：登录 → 查询航班 → 创建出行人 → 下单

        自动完成完整的预订流程。

        Args:
            username: 用户名
            password: 密码
            from_city: 出发城市/机场代码（如 PEK、PVG）
            to_city: 目的地城市/机场代码（如 JFK、LHR）
            from_date: 出发日期（yyyy-MM-dd）
            passenger_infos: 出行人信息列表
            contact: 联系人信息 {name, phone, email}
            flight_index: 要预订的航班索引（从搜索结果中选择）
            trip_type: 行程类型（1=单程 2=往返）
            cabin: 舱位（Y=经济 C=商务 F=头等）
            return_date: 返程日期（往返时必填）

        Returns:
            {"success": bool, "message": str, "order_id": str, "data": {...}}
        """
        logger.info(f"[一键预订] {from_city} -> {to_city}, {from_date}")

        # 步骤 4：登录
        login_result = await self.login_user(username, password)
        if not login_result["success"]:
            return {"success": False, "message": f"登录失败: {login_result['message']}"}

        # 步骤 5：查询航班
        search_result = await self.search_intl_flights(
            from_city=from_city,
            to_city=to_city,
            from_date=from_date,
            trip_type=trip_type,
            cabin=cabin,
            return_date=return_date,
        )
        if not search_result["success"]:
            return {"success": False, "message": f"航班查询失败: {search_result['message']}"}

        flights = search_result.get("flights", [])
        if not flights:
            return {"success": False, "message": "未找到航班"}

        # 选择航班
        if flight_index >= len(flights):
            flight_index = 0  # 默认选择第一个

        selected_flight = flights[flight_index]
        flight_id = selected_flight.get("flightId", selected_flight.get("flightID", ""))
        serial_number = search_result.get("serialNumber", "")

        logger.info(f"[一键预订] 选择航班: flight_id={flight_id}, serial_number={serial_number}")

        # 步骤 6：创建出行人
        passenger_ids = []
        for pax in passenger_infos:
            pax_result = await self.create_passenger(**pax)
            if not pax_result["success"]:
                return {
                    "success": False,
                    "message": f"创建出行人失败: {pax_result['message']}",
                }
            passenger_ids.append(pax_result["passenger_id"])

        # 构建 flight_selection
        flight_selection = {
            "flightId": flight_id,
            "serialNumber": serial_number,
            "flightData": selected_flight,
            "searchParams": search_result.get("searchParams", {}),
        }

        # 步骤 7：下单
        return await self.book_intl_flight(
            flight_id=flight_id,
            serial_number=serial_number,
            passenger_ids=passenger_ids,
            contact_name=contact["name"],
            contact_phone=contact["phone"],
            contact_email=contact.get("email"),
            policy_serial_number=serial_number,
            flight_data=selected_flight,
            search_params=search_result.get("searchParams", {}),
            passenger_infos=passenger_infos,
        )
