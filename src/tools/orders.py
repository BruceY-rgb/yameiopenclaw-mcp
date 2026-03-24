"""
订单相关MCP工具

提供机票预订、订单查询、支付、取消等功能。
"""

import logging
from typing import List, Optional
from pydantic import BaseModel, Field
from fastmcp import FastMCP

from src.api.client import MeiyaApiClient
from src.workflow.orchestrator import WorkflowOrchestrator

logger = logging.getLogger(__name__)


# ===========================================
# 数据模型
# ===========================================

class PassengerInfo(BaseModel):
    """乘客信息（用于预订）"""
    passenger_id: Optional[str] = Field(None, description="出行人ID（已有出行人时使用）")
    # 以下字段用于创建新出行人
    name: Optional[str] = Field(None, description="乘客姓名")
    passenger_type: Optional[str] = Field(
        None,
        description="乘客类型: adult/child/infant",
        pattern="^(adult|child|infant)$"
    )
    nationality: Optional[str] = Field(None, description="国籍", pattern="^[A-Z]{2}$")
    id_type: Optional[str] = Field(None, description="证件类型")
    id_number: Optional[str] = Field(None, description="证件号码")
    id_expiration: Optional[str] = Field(None, description="证件有效期")
    gender: Optional[str] = Field(None, description="性别: 1/0")
    birthday: Optional[str] = Field(None, description="出生日期")
    phone_number: Optional[str] = Field(None, description="手机号")
    email: Optional[str] = Field(None, description="邮箱")


class ContactInfo(BaseModel):
    """联系人信息"""
    name: str = Field(..., description="联系人姓名")
    phone: str = Field(..., description="联系人电话")
    email: Optional[str] = Field(None, description="联系人邮箱")


class BookTicketInput(BaseModel):
    """预订机票输入"""
    flight_id: str = Field(..., description="航班ID（从search_international_flights返回）")
    passengers: List[PassengerInfo] = Field(
        ...,
        description="乘客列表",
        min_length=1
    )
    contact: ContactInfo = Field(..., description="联系人信息")
    cabin_class: str = Field(
        default="economy",
        description="舱位等级: economy/business/first"
    )
    create_order_type: int = Field(
        default=1,
        description="下单方式: 1=实时航班, 2=PNR, 3=航段",
        ge=1,
        le=3
    )


class BookTicketOutput(BaseModel):
    """预订机票输出"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(default="", description="提示信息")
    order_id: Optional[str] = Field(None, description="订单号")
    status: Optional[str] = Field(None, description="订单状态")
    total_amount: Optional[float] = Field(None, description="订单总金额")
    currency: Optional[str] = Field(None, description="货币类型")
    payment_url: Optional[str] = Field(None, description="支付链接")
    pnr: Optional[str] = Field(None, description="PNR编码")


class QueryOrderInput(BaseModel):
    """查询订单输入"""
    order_id: str = Field(..., description="订单号")


class QueryOrderOutput(BaseModel):
    """查询订单输出"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(default="", description="提示信息")
    data: Optional[dict] = Field(None, description="订单详情")


class PayOrderInput(BaseModel):
    """支付订单输入"""
    order_id: str = Field(..., description="订单号")
    payment_method: str = Field(
        default="online",
        description="支付方式: online（在线支付）/ offline（线下支付）"
    )


class PayOrderOutput(BaseModel):
    """支付订单输出"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(default="", description="提示信息")
    data: Optional[dict] = Field(None, description="支付结果")


class CancelOrderInput(BaseModel):
    """取消订单输入"""
    order_id: str = Field(..., description="订单号")
    reason: Optional[str] = Field(None, description="取消原因")


class CancelOrderOutput(BaseModel):
    """取消订单输出"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(default="", description="提示信息")
    data: Optional[dict] = Field(None, description="取消结果")


# ===========================================
# 工具注册函数
# ===========================================

def register_order_tools(
    mcp: FastMCP,
    api_client: MeiyaApiClient,
    workflow: Optional[WorkflowOrchestrator] = None
):
    """注册订单相关工具"""

    @mcp.tool()
    async def book_ticket(input: BookTicketInput) -> BookTicketOutput:
        """
        预订国际机票（完整流程）

        执行完整的机票预订流程，包括：
        1. 航班计价
        2. 创建出行人（如需要）
        3. 生单
        4. 验价验舱

        这是一个原子操作，如果任何步骤失败，会自动进行错误处理。

        Args:
            flight_id: 航班ID（从search_international_flights返回）
            passengers: 乘客信息列表
            contact: 联系人信息
            cabin_class: 舱位等级
            create_order_type: 下单方式

        Returns:
            订单信息，包含order_id和payment_url

        使用示例:
        {
            "flight_id": "FL123456",
            "passengers": [
                {
                    "name": "张三",
                    "passenger_type": "adult",
                    "nationality": "CN",
                    "id_type": "0",
                    "id_number": "E12345678",
                    "id_expiration": "2030-01-01",
                    "gender": "1",
                    "birthday": "1990-01-01",
                    "phone_number": "13800138000"
                }
            ],
            "contact": {
                "name": "张三",
                "phone": "13800138000",
                "email": "zhangsan@example.com"
            }
        }
        """
        if not workflow:
            logger.error("工作流编排器未初始化")
            return BookTicketOutput(
                success=False,
                message="服务未正确初始化"
            )

        try:
            logger.info(
                f"开始预订机票: flight_id={input.flight_id}, "
                f"乘客数={len(input.passengers)}"
            )

            # 准备乘客数据
            passengers_data = []
            for pax in input.passengers:
                if pax.passenger_id:
                    # 已有出行人
                    passengers_data.append({"passengerId": pax.passenger_id})
                else:
                    # 需要创建新出行人
                    pax_data = {
                        "name": pax.name,
                        "passengerType": pax.passenger_type or "adult",
                        "nationality": pax.nationality or "CN",
                        "idType": pax.id_type or "0",
                        "idNumber": pax.id_number,
                        "idExpiration": pax.id_expiration,
                        "gender": pax.gender,
                        "birthday": pax.birthday
                    }
                    if pax.phone_number:
                        pax_data["phoneNumber"] = pax.phone_number
                    if pax.email:
                        pax_data["email"] = pax.email
                    passengers_data.append(pax_data)

            # 准备联系人数据
            contact_data = input.contact.model_dump()

            # 使用工作流编排器执行完整流程
            result = await workflow.execute_booking_workflow({
                "flight_id": input.flight_id,
                "passengers": passengers_data,
                "contact": contact_data,
                "cabin_class": input.cabin_class,
                "create_order_type": input.create_order_type
            })

            logger.info(f"预订成功: order_id={result.get('order_id')}")

            return BookTicketOutput(
                success=result.get("success", False),
                message=result.get("message", "预订成功"),
                order_id=result.get("order_id"),
                status=result.get("status"),
                total_amount=result.get("total_amount"),
                currency=result.get("currency", "CNY"),
                payment_url=result.get("payment_url"),
                pnr=result.get("pnr")
            )

        except Exception as e:
            logger.error(f"预订失败: {e}")
            return BookTicketOutput(
                success=False,
                message=f"预订失败: {str(e)}"
            )

    @mcp.tool()
    async def query_order(input: QueryOrderInput) -> QueryOrderOutput:
        """
        查询订单详情

        获取订单的详细信息，包括：
        - 订单状态（待支付、已支付、已出票等）
        - 航班信息
        - 乘客信息
        - 价格明细
        - 支付信息

        Args:
            order_id: 订单号

        Returns:
            订单详情
        """
        try:
            logger.info(f"查询订单: order_id={input.order_id}")

            response = await api_client.query_order(input.order_id)

            return QueryOrderOutput(
                success=True,
                message="查询成功",
                data=response.get("data", {})
            )

        except Exception as e:
            logger.error(f"查询订单失败: {e}")
            return QueryOrderOutput(
                success=False,
                message=f"查询失败: {str(e)}"
            )

    @mcp.tool()
    async def pay_order(input: PayOrderInput) -> PayOrderOutput:
        """
        支付订单

        对订单进行支付操作。
        先进行验价验舱，然后确认支付。

        Args:
            order_id: 订单号
            payment_method: 支付方式: online（在线支付）/ offline（线下支付）

        Returns:
            支付结果，包含支付链接（在线支付）
        """
        if not workflow:
            logger.error("工作流编排器未初始化")
            return PayOrderOutput(
                success=False,
                message="服务未正确初始化"
            )

        try:
            logger.info(f"支付订单: order_id={input.order_id}")

            # 使用工作流执行支付
            result = await workflow.execute_payment_workflow(
                input.order_id,
                input.payment_method
            )

            return PayOrderOutput(
                success=result.get("success", False),
                message=result.get("message", "支付成功"),
                data=result.get("data", {})
            )

        except Exception as e:
            logger.error(f"支付失败: {e}")
            return PayOrderOutput(
                success=False,
                message=f"支付失败: {str(e)}"
            )

    @mcp.tool()
    async def cancel_order(input: CancelOrderInput) -> CancelOrderOutput:
        """
        取消订单

        取消未支付或已支付的订单。
        注意：已出票的订单可能需要走退票流程。

        Args:
            order_id: 订单号
            reason: 取消原因（可选）

        Returns:
            取消结果
        """
        if not workflow:
            logger.error("工作流编排器未初始化")
            return CancelOrderOutput(
                success=False,
                message="服务未正确初始化"
            )

        try:
            logger.info(f"取消订单: order_id={input.order_id}")

            result = await workflow.execute_cancel_workflow(
                input.order_id,
                input.reason
            )

            return CancelOrderOutput(
                success=result.get("success", False),
                message=result.get("message", "取消成功"),
                data=result.get("data", {})
            )

        except Exception as e:
            logger.error(f"取消订单失败: {e}")
            return CancelOrderOutput(
                success=False,
                message=f"取消失败: {str(e)}"
            )

    @mcp.tool()
    async def get_flight_change() -> dict:
        """
        查询航变信息

        查询客户部门的航班变更消息，包括延误、取消、时刻变更等。

        Returns:
            航变信息列表
        """
        try:
            logger.info("查询航变信息")

            response = await api_client.get_flight_change()

            return {
                "success": True,
                "message": "查询成功",
                "data": response.get("data", {})
            }

        except Exception as e:
            logger.error(f"查询航变失败: {e}")
            return {
                "success": False,
                "message": f"查询失败: {str(e)}"
            }

    logger.info("订单工具注册完成")
