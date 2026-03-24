"""
航班相关MCP工具

提供航班查询、详情获取、计价等功能。
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

class SearchFlightsInput(BaseModel):
    """查询航班输入"""
    origin: str = Field(
        ...,
        description="出发地机场代码，如PEK（北京首都）、PVG（上海浦东）、CAN（广州白云）",
        pattern="^[A-Z]{3}$",
        examples=["PEK", "PVG", "CAN", "JFK", "LHR"]
    )
    destination: str = Field(
        ...,
        description="目的地机场代码，如JFK（纽约肯尼迪）、LHR（伦敦希思罗）、NRT（东京）",
        pattern="^[A-Z]{3}$",
        examples=["JFK", "LHR", "NRT", "CDG", "SFO"]
    )
    departure_date: str = Field(
        ...,
        description="出发日期，格式YYYY-MM-DD",
        pattern="^\\d{4}-\\d{2}-\\d{2}$",
        examples=["2026-04-01", "2026-05-15"]
    )
    adults: int = Field(
        default=1,
        description="成人数量（1-9）",
        ge=1,
        le=9
    )
    children: int = Field(
        default=0,
        description="儿童数量（2-12岁）",
        ge=0,
        le=5
    )
    infants: int = Field(
        default=0,
        description="婴儿数量（0-2岁）",
        ge=0,
        le=2
    )
    cabin_class: str = Field(
        default="economy",
        description="舱位等级: economy（经济舱）/ business（商务舱）/ first（头等舱）",
        pattern="^(economy|business|first)$"
    )
    trip_type: str = Field(
        default="one_way",
        description="行程类型: one_way（单程）/ round_trip（往返）",
        pattern="^(one_way|round_trip)$"
    )
    return_date: Optional[str] = Field(
        None,
        description="返程日期（往返时必填），格式YYYY-MM-DD",
        pattern="^\\d{4}-\\d{2}-\\d{2}$"
    )


class SearchFlightsOutput(BaseModel):
    """查询航班输出"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(default="", description="提示信息")
    total: int = Field(default=0, description="航班总数")
    flights: List[dict] = Field(default_factory=list, description="航班列表")
    search_id: Optional[str] = Field(None, description="搜索ID（用于异步查询）")


class FlightDetailsInput(BaseModel):
    """获取航班详情输入"""
    flight_id: str = Field(
        ...,
        description="航班ID（从search_international_flights返回）",
        examples=["FL123456", "flight_abc123"]
    )


class FlightDetailsOutput(BaseModel):
    """获取航班详情输出"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(default="", description="提示信息")
    data: Optional[dict] = Field(None, description="航班详情")


class PricingInput(BaseModel):
    """航班计价输入"""
    flight_id: str = Field(
        ...,
        description="航班ID",
        examples=["FL123456"]
    )
    cabin_class: str = Field(
        default="economy",
        description="舱位等级: economy/business/first",
        pattern="^(economy|business|first)$"
    )
    adults: int = Field(default=1, description="成人数量", ge=1, le=9)
    children: int = Field(default=0, description="儿童数量", ge=0, le=5)
    infants: int = Field(default=0, description="婴儿数量", ge=0, le=2)


class PricingOutput(BaseModel):
    """航班计价输出"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(default="", description="提示信息")
    data: Optional[dict] = Field(None, description="计价结果")


class TicketRuleInput(BaseModel):
    """退改签规则查询输入"""
    flight_id: str = Field(..., description="航班ID")
    cabin_class: str = Field(default="economy", description="舱位等级")


class TicketRuleOutput(BaseModel):
    """退改签规则查询输出"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(default="", description="提示信息")
    data: Optional[dict] = Field(None, description="退改签规则")


# ===========================================
# 工具注册函数
# ===========================================

def register_flight_tools(
    mcp: FastMCP,
    api_client: MeiyaApiClient,
    workflow: Optional[WorkflowOrchestrator] = None
):
    """注册航班相关工具"""

    @mcp.tool()
    async def search_international_flights(input: SearchFlightsInput) -> SearchFlightsOutput:
        """
        查询国际航班

        根据出发地、目的地和日期查询可用的国际航班。
        支持单程和往返查询，可以指定乘客数量和舱位等级。

        返回航班列表，包含航班号、起降时间、价格、舱位等信息。
        如果数据量大，会返回search_id用于异步获取完整结果。

        使用示例:
        - 北京到纽约单程: origin="PEK", destination="JFK", departure_date="2026-04-01"
        - 上海到伦敦往返: origin="PVG", destination="LHR", trip_type="round_trip", return_date="2026-04-10"
        """
        try:
            logger.info(
                f"查询航班: {input.origin} -> {input.destination}, "
                f"日期: {input.departure_date}, 成人: {input.adults}"
            )

            # 调用Shopping接口
            response = await api_client.search_flights(
                origin=input.origin,
                destination=input.destination,
                departure_date=input.departure_date,
                adults=input.adults,
                children=input.children,
                infants=input.infants,
                cabin_class=input.cabin_class,
                trip_type=input.trip_type,
                return_date=input.return_date
            )

            data = response.get("data", {})

            # 检查是否异步返回
            if "searchId" in data:
                return SearchFlightsOutput(
                    success=True,
                    message="查询已提交，请使用search_id获取结果",
                    search_id=data["searchId"]
                )

            # 同步返回结果
            flights = data.get("flights", [])

            logger.info(f"查询成功，找到 {len(flights)} 个航班")

            return SearchFlightsOutput(
                success=True,
                message=f"找到 {len(flights)} 个航班",
                total=len(flights),
                flights=flights
            )

        except Exception as e:
            logger.error(f"查询航班失败: {e}")
            return SearchFlightsOutput(
                success=False,
                message=f"查询失败: {str(e)}"
            )

    @mcp.tool()
    async def get_flight_details(input: FlightDetailsInput) -> FlightDetailsOutput:
        """
        获取航班详情

        根据航班ID获取详细的航班信息，包括：
        - 航班号、航空公司
        - 起降时间、机场
        - 机型、餐食
        - 行李额度
        - 退改签规则

        Args:
            flight_id: 航班ID（从search_international_flights返回）

        Returns:
            航班详细信息
        """
        try:
            logger.info(f"获取航班详情: flight_id={input.flight_id}")

            response = await api_client.get_flight_details(input.flight_id)

            return FlightDetailsOutput(
                success=True,
                message="获取成功",
                data=response.get("data", {})
            )

        except Exception as e:
            logger.error(f"获取航班详情失败: {e}")
            return FlightDetailsOutput(
                success=False,
                message=f"获取失败: {str(e)}"
            )

    @mcp.tool()
    async def pricing_flight(input: PricingInput) -> PricingOutput:
        """
        航班计价

        对指定航班进行计价，获取准确的价格信息。
        价格包含：票面价、税费、燃油附加费等。

        返回policySerialNumber，用于下单时使用。

        Args:
            flight_id: 航班ID
            cabin_class: 舱位等级
            passengers: 乘客数量配置

        Returns:
            价格详情，包含policySerialNumber（下单时需要）

        使用示例:
        {
            "flight_id": "FL123456",
            "cabin_class": "economy",
            "adults": 1,
            "children": 0,
            "infants": 0
        }
        """
        try:
            logger.info(f"计价: flight_id={input.flight_id}, cabin={input.cabin_class}")

            passengers = {
                "adults": input.adults,
                "children": input.children,
                "infants": input.infants
            }

            response = await api_client.pricing(
                flight_id=input.flight_id,
                cabin_class=input.cabin_class,
                passengers=passengers
            )

            data = response.get("data", {})
            logger.info(f"计价成功: policy_serial_number={data.get('policySerialNumber')}")

            return PricingOutput(
                success=True,
                message="计价成功",
                data=data
            )

        except Exception as e:
            logger.error(f"计价失败: {e}")
            return PricingOutput(
                success=False,
                message=f"计价失败: {str(e)}"
            )

    @mcp.tool()
    async def query_ticket_rule(input: TicketRuleInput) -> TicketRuleOutput:
        """
        查询退改签规则

        查询航班的退票、改签、签转规则及费用。

        Args:
            flight_id: 航班ID
            cabin_class: 舱位等级

        Returns:
            退改签规则详情
        """
        try:
            logger.info(f"查询退改签规则: flight_id={input.flight_id}")

            response = await api_client.query_ticket_rule(
                flight_id=input.flight_id,
                cabin_class=input.cabin_class
            )

            return TicketRuleOutput(
                success=True,
                message="查询成功",
                data=response.get("data", {})
            )

        except Exception as e:
            logger.error(f"查询退改签规则失败: {e}")
            return TicketRuleOutput(
                success=False,
                message=f"查询失败: {str(e)}"
            )

    @mcp.tool()
    async def get_more_price(flight_id: str, cabin_class: str = "economy") -> dict:
        """
        获取更多价格（全舱位）

        获取航班所有舱位的价格信息，方便比较。

        Args:
            flight_id: 航班ID
            cabin_class: 舱位等级

        Returns:
            所有舱位的价格列表
        """
        try:
            logger.info(f"获取更多价格: flight_id={flight_id}")

            response = await api_client.get_more_price(flight_id, cabin_class)

            return {
                "success": True,
                "message": "获取成功",
                "data": response.get("data", {})
            }

        except Exception as e:
            logger.error(f"获取更多价格失败: {e}")
            return {
                "success": False,
                "message": f"获取失败: {str(e)}"
            }

    @mcp.tool()
    async def query_stopover(flight_id: str) -> dict:
        """
        查询经停信息

        查询航班是否有经停，以及经停详情。

        Args:
            flight_id: 航班ID

        Returns:
            经停信息
        """
        try:
            logger.info(f"查询经停: flight_id={flight_id}")

            response = await api_client.query_stopover(flight_id)

            return {
                "success": True,
                "message": "查询成功",
                "data": response.get("data", {})
            }

        except Exception as e:
            logger.error(f"查询经停失败: {e}")
            return {
                "success": False,
                "message": f"查询失败: {str(e)}"
            }

    logger.info("航班工具注册完成")
