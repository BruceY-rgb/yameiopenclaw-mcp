"""
账号与订单相关 MCP 工具

提供以下能力：
  - 创建用户账号（步骤 3）：POST /api/open/createUser（公司密钥鉴权）
  - 国际机票下单（步骤 7）：POST /supplier/.../TOOrderSave
  - 完整预订流程（步骤 4-7 串联）
"""

import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from fastmcp import FastMCP

from src.api.client import OntuotuApiClient
from src.workflow.orchestrator import WorkflowOrchestrator

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════
# 数据模型
# ═══════════════════════════════════════════════

class CreateUserInput(BaseModel):
    """创建用户账号输入（步骤 3）"""
    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")
    real_name: Optional[str] = Field(None, description="真实姓名（可选）")
    phone: Optional[str] = Field(None, description="手机号（可选）")
    email: Optional[str] = Field(None, description="邮箱（可选）")


class CreateUserOutput(BaseModel):
    """创建用户账号输出"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(default="", description="提示信息")
    data: Optional[Dict[str, Any]] = Field(None, description="创建结果")


class PassengerRef(BaseModel):
    """下单时的出行人引用"""
    passenger_id: str = Field(..., description="出行人 ID（由 create_passenger 返回）")


class BookIntlFlightInput(BaseModel):
    """国际机票下单输入（步骤 7）"""
    flight_id: str = Field(
        ...,
        description="航班 ID（来自 search_international_flights 结果）"
    )
    serial_number: str = Field(
        ...,
        description="序列号（来自 search_international_flights 结果）"
    )
    passenger_ids: List[str] = Field(
        ...,
        description="出行人 ID 列表（由 create_passenger 返回）",
        min_length=1
    )
    contact_name: str = Field(..., description="联系人姓名")
    contact_phone: str = Field(..., description="联系人电话")
    contact_email: Optional[str] = Field(None, description="联系人邮箱（可选）")
    policy_serial_number: Optional[str] = Field(
        None,
        description="策略序列号（计价后获取，可选）"
    )


class BookIntlFlightOutput(BaseModel):
    """国际机票下单输出"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(default="", description="提示信息")
    order_id: str = Field(default="", description="订单 ID")
    data: Optional[Dict[str, Any]] = Field(None, description="下单结果详情")


class PassengerInfo(BaseModel):
    """完整预订流程中的出行人信息"""
    name: str = Field(..., description="姓名")
    passenger_type: int = Field(default=0, description="乘客类型：0=成人 1=儿童 2=婴儿")
    nationality: str = Field(..., description="国籍二字码，如 CN")
    id_type: str = Field(..., description="证件类型：0=护照 等")
    id_number: str = Field(..., description="证件号码")
    id_expiration: str = Field(..., description="证件有效期（yyyy-MM-dd）")
    gender: int = Field(..., description="性别：1=男 0=女")
    birthday: str = Field(..., description="出生日期（yyyy-MM-dd）")
    phone: Optional[str] = Field(None, description="手机号（可选）")
    email: Optional[str] = Field(None, description="邮箱（可选）")


class FullBookingInput(BaseModel):
    """完整预订流程输入（步骤 4-7 串联）"""
    username: str = Field(..., description="用户名（步骤 3 创建）")
    password: str = Field(..., description="密码（步骤 3 创建）")
    flight_id: str = Field(..., description="航班 ID（来自 search_international_flights）")
    serial_number: str = Field(..., description="序列号（来自 search_international_flights）")
    passengers: List[PassengerInfo] = Field(..., description="出行人信息列表", min_length=1)
    contact_name: str = Field(..., description="联系人姓名")
    contact_phone: str = Field(..., description="联系人电话")
    contact_email: Optional[str] = Field(None, description="联系人邮箱（可选）")
    policy_serial_number: Optional[str] = Field(None, description="策略序列号（可选）")


class FullBookingOutput(BaseModel):
    """完整预订流程输出"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(default="", description="提示信息")
    order_id: str = Field(default="", description="订单 ID")
    data: Optional[Dict[str, Any]] = Field(None, description="下单结果详情")


# ═══════════════════════════════════════════════
# 工具注册
# ═══════════════════════════════════════════════

def register_order_tools(
    mcp: FastMCP,
    api_client: OntuotuApiClient,
    workflow: Optional[WorkflowOrchestrator] = None,
):
    """注册账号与订单相关 MCP 工具"""

    @mcp.tool()
    async def create_user_account(input: CreateUserInput) -> CreateUserOutput:
        """
        创建用户账号（步骤 3）

        使用公司 AppKey/AppSecret 调用开放接口 /api/open/user/create，
        为小龙虾创建一个可以登录的用户账号。

        前置条件：
          - 已在环境变量中配置 ONTUOTU_APP_KEY 和 ONTUOTU_APP_SECRET

        创建成功后，使用返回的 username/password 调用 login_user（步骤 4）。

        使用示例：
          {
            "username": "user001",
            "password": "Pass@123",
            "real_name": "张三",
            "phone": "13800138000"
          }
        """
        if not workflow:
            return CreateUserOutput(success=False, message="服务未初始化")

        try:
            result = await workflow.create_user_account(
                username=input.username,
                password=input.password,
                real_name=input.real_name,
                phone=input.phone,
                email=input.email,
            )
            return CreateUserOutput(
                success=result["success"],
                message=result["message"],
                data=result.get("data"),
            )
        except Exception as e:
            logger.error(f"创建用户账号失败: {e}")
            return CreateUserOutput(success=False, message=str(e))

    @mcp.tool()
    async def book_international_flight(
        input: BookIntlFlightInput,
    ) -> BookIntlFlightOutput:
        """
        国际机票下单（步骤 7）

        调用 /supplier/supplierapi/thgeneralinterface/SupplierIntlToOrder/v2/TOOrderSave 接口，使用已创建的出行人 ID 完成下单。

        前置条件：
          - 已通过 login_user 完成登录（步骤 4）
          - 已通过 search_international_flights 获取 flight_id 和 serial_number（步骤 5）
          - 已通过 create_passenger 创建出行人并获取 passenger_id（步骤 6）

        使用示例：
          {
            "flight_id": "FL123456",
            "serial_number": "SN20260601001",
            "passenger_ids": ["PAX001", "PAX002"],
            "contact_name": "张三",
            "contact_phone": "13800138000",
            "contact_email": "zhangsan@example.com"
          }
        """
        if not workflow:
            return BookIntlFlightOutput(success=False, message="服务未初始化")

        try:
            result = await workflow.book_intl_flight(
                flight_id=input.flight_id,
                serial_number=input.serial_number,
                passenger_ids=input.passenger_ids,
                contact_name=input.contact_name,
                contact_phone=input.contact_phone,
                contact_email=input.contact_email,
                policy_serial_number=input.policy_serial_number,
            )
            return BookIntlFlightOutput(
                success=result["success"],
                message=result["message"],
                order_id=result.get("order_id", ""),
                data=result.get("data"),
            )
        except Exception as e:
            logger.error(f"国际机票下单失败: {e}")
            return BookIntlFlightOutput(success=False, message=str(e))

    @mcp.tool()
    async def full_booking_workflow(input: FullBookingInput) -> FullBookingOutput:
        """
        完整预订流程（步骤 4-7 串联）

        自动执行以下步骤：
          4. 使用用户账号密码登录，获取 Token
          6. 为每个出行人调用 create_passenger 创建出行人
          7. 使用出行人 ID 调用 intlsaveOrder 完成下单

        适合一次性完成整个预订流程，无需手动调用多个工具。

        前置条件：
          - 已通过 create_user_account 创建了用户账号（步骤 3）
          - 已通过 search_international_flights 获取了 flight_id 和 serial_number（步骤 5）

        使用示例：
          {
            "username": "user001",
            "password": "Pass@123",
            "flight_id": "FL123456",
            "serial_number": "SN20260601001",
            "passengers": [
              {
                "name": "张三",
                "passenger_type": 0,
                "nationality": "CN",
                "id_type": "0",
                "id_number": "E12345678",
                "id_expiration": "2030-01-01",
                "gender": 1,
                "birthday": "1990-01-01"
              }
            ],
            "contact_name": "张三",
            "contact_phone": "13800138000"
          }
        """
        if not workflow:
            return FullBookingOutput(success=False, message="服务未初始化")

        try:
            passenger_infos = [
                {
                    "name": p.name,
                    "passenger_type": p.passenger_type,
                    "nationality": p.nationality,
                    "id_type": p.id_type,
                    "id_number": p.id_number,
                    "id_expiration": p.id_expiration,
                    "gender": p.gender,
                    "birthday": p.birthday,
                    "phone": p.phone,
                    "email": p.email,
                }
                for p in input.passengers
            ]

            result = await workflow.execute_full_booking(
                username=input.username,
                password=input.password,
                search_params={},  # 已有 flight_id，无需再查询
                passenger_infos=passenger_infos,
                contact={
                    "name": input.contact_name,
                    "phone": input.contact_phone,
                    "email": input.contact_email,
                },
                flight_selection={
                    "flightId": input.flight_id,
                    "serialNumber": input.serial_number,
                    "policySerialNumber": input.policy_serial_number,
                },
            )

            return FullBookingOutput(
                success=result["success"],
                message=result["message"],
                order_id=result.get("order_id", ""),
                data=result.get("data"),
            )
        except Exception as e:
            logger.error(f"完整预订流程失败: {e}")
            return FullBookingOutput(success=False, message=str(e))

    logger.info(
        "订单工具注册完成（create_user_account / book_international_flight / full_booking_workflow）"
    )
