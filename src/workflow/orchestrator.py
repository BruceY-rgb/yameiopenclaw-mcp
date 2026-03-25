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
            username: 用户名
            password: 密码
            real_name: 真实姓名（可选）
            phone: 手机号（可选）
            email: 邮箱（可选）
            extra: 其他扩展字段

        Returns:
            {"success": bool, "message": str, "data": {...}}
        """
        logger.info(f"[步骤3] 创建用户账号: {username}")
        try:
            resp = await self.api_client.create_user(
                username=username,
                password=password,
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
            logger.error(f"[步骤3] 创建用户账号失败: {e}")
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
    # 步骤 5：查询国际机票
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
        """步骤 5：使用 Token 查询国际机票分页

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
            {"success": bool, "message": str, "data": {...}}
        """
        logger.info(f"[步骤5] 查询国际机票: {from_city} -> {to_city}, {from_date}")
        body: Dict[str, Any] = {
            "tripType": trip_type,
            "fromCity": from_city,
            "toCity": to_city,
            "fromDate": from_date,
            "adultCount": adult_count,
            "childCount": child_count,
            "infantCount": infant_count,
            "cabin": cabin,
        }
        if return_date:
            body["returnDate"] = return_date
        if extra:
            body.update(extra)

        try:
            resp = await self.api_client.search_intl_flights(body)
            return {"success": True, "message": "查询成功", "data": resp}
        except Exception as e:
            logger.error(f"[步骤5] 查询国际机票失败: {e}")
            return {"success": False, "message": str(e), "data": None}

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
        body: Dict[str, Any] = {
            "name": name,
            "passengerType": passenger_type,
            "nationality": nationality,
            "idType": id_type,
            "idNumber": id_number,
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
            data = resp.get("value") or resp.get("data") or resp
            passenger_id = (
                data.get("passengerId") or data.get("id") or ""
                if isinstance(data, dict) else ""
            )
            logger.info(f"[步骤6] 创建出行人成功: passenger_id={passenger_id}")
            return {
                "success": True,
                "message": "出行人创建成功",
                "passenger_id": passenger_id,
                "data": data,
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
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """步骤 7：使用 Token 国际机票下单

        Args:
            flight_id: 航班 ID（来自 intlsearch 结果）
            serial_number: 序列号（来自 intlsearch 结果）
            passenger_ids: 出行人 ID 列表（步骤 6 创建后获取）
            contact_name: 联系人姓名
            contact_phone: 联系人电话
            contact_email: 联系人邮箱（可选）
            policy_serial_number: 策略序列号（计价后获取，可选）
            extra: 其他扩展字段

        Returns:
            {"success": bool, "message": str, "order_id": str, "data": {...}}
        """
        logger.info(
            f"[步骤7] 国际机票下单: flight_id={flight_id}, "
            f"passengers={passenger_ids}"
        )
        body: Dict[str, Any] = {
            "flightId": flight_id,
            "serialNumber": serial_number,
            "passengerList": [{"passengerId": pid} for pid in passenger_ids],
            "contactName": contact_name,
            "contactPhone": contact_phone,
        }
        if contact_email:
            body["contactEmail"] = contact_email
        if policy_serial_number:
            body["policySerialNumber"] = policy_serial_number
        if extra:
            body.update(extra)

        try:
            resp = await self.api_client.save_intl_order(body)
            data = resp.get("value") or resp.get("data") or resp
            order_id = (
                data.get("orderId") or data.get("id") or ""
                if isinstance(data, dict) else ""
            )
            logger.info(f"[步骤7] 下单成功: order_id={order_id}")
            return {
                "success": True,
                "message": "下单成功",
                "order_id": order_id,
                "data": data,
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
            flight_selection: 选定的航班信息 {flightId, serialNumber, policySerialNumber}

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
        return await self.book_intl_flight(
            flight_id=flight_selection["flightId"],
            serial_number=flight_selection["serialNumber"],
            passenger_ids=passenger_ids,
            contact_name=contact["name"],
            contact_phone=contact["phone"],
            contact_email=contact.get("email"),
            policy_serial_number=flight_selection.get("policySerialNumber"),
        )
