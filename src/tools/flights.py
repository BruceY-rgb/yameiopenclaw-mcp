"""
航班相关 MCP 工具

提供以下能力：
  - 用户登录（步骤 4）
  - 国际机票查询（步骤 5）
  - 国际机票退改签条款查询
  - 国际机票订单详情查询
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

class LoginInput(BaseModel):
    """用户登录输入（步骤 4）"""
    username: str = Field(..., description="用户名（由步骤 3 创建）")
    password: str = Field(..., description="密码（由步骤 3 创建）")
    force_refresh: bool = Field(
        default=False,
        description="是否强制重新登录（忽略缓存）"
    )


class LoginOutput(BaseModel):
    """用户登录输出"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(default="", description="提示信息")
    token: str = Field(default="", description="登录 Token（后续请求自动携带）")


class SearchIntlFlightsInput(BaseModel):
    """国际机票查询输入（步骤 5）"""
    from_city: str = Field(
        ...,
        description="出发城市/机场代码，如 PEK（北京）、PVG（上海）、CAN（广州）",
        examples=["PEK", "PVG", "CAN"]
    )
    to_city: str = Field(
        ...,
        description="目的地城市/机场代码，如 JFK（纽约）、LHR（伦敦）、NRT（东京）",
        examples=["JFK", "LHR", "NRT"]
    )
    from_date: str = Field(
        ...,
        description="出发日期，格式 yyyy-MM-dd",
        pattern="^\\d{4}-\\d{2}-\\d{2}$",
        examples=["2026-05-01"]
    )
    trip_type: int = Field(
        default=1,
        description="行程类型：1=单程，2=往返",
        ge=1,
        le=2
    )
    adult_count: int = Field(default=1, description="成人数量", ge=1, le=9)
    child_count: int = Field(default=0, description="儿童数量（2-12岁）", ge=0, le=5)
    infant_count: int = Field(default=0, description="婴儿数量（0-2岁）", ge=0, le=2)
    cabin: str = Field(
        default="Y",
        description="舱位：Y=经济舱，C=商务舱，F=头等舱",
        pattern="^[YCF]$"
    )
    return_date: Optional[str] = Field(
        None,
        description="返程日期（往返时必填），格式 yyyy-MM-dd",
        pattern="^\\d{4}-\\d{2}-\\d{2}$"
    )


class SearchIntlFlightsOutput(BaseModel):
    """国际机票查询输出"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(default="", description="提示信息")
    data: Optional[Dict[str, Any]] = Field(None, description="查询结果（含航班列表）")


class QueryIntlTicketRuleInput(BaseModel):
    """国际机票退改签条款查询输入"""
    body: Dict[str, Any] = Field(
        ...,
        description="查询参数（参考 /api/flight/queryIntlShoppingRule 接口文档）"
    )


class QueryIntlOrderDetailInput(BaseModel):
    """国际机票订单详情查询输入"""
    body: Dict[str, Any] = Field(
        ...,
        description="查询参数（参考 /api/flight/intldetail 接口文档）"
    )


class GenericOutput(BaseModel):
    """通用输出"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(default="", description="提示信息")
    data: Optional[Dict[str, Any]] = Field(None, description="响应数据")


# ═══════════════════════════════════════════════
# 工具注册
# ═══════════════════════════════════════════════

def register_flight_tools(
    mcp: FastMCP,
    api_client: OntuotuApiClient,
    workflow: Optional[WorkflowOrchestrator] = None,
):
    """注册航班相关 MCP 工具"""

    @mcp.tool()
    async def login_user(input: LoginInput) -> LoginOutput:
        """
        用户登录（步骤 4）

        使用用户账号密码调用登录接口，获取 Token。
        Token 会自动缓存并注入到后续所有请求中，无需手动传递。

        前置条件：
          - 已通过步骤 3（create_user_account）创建了用户账号

        使用示例：
          {"username": "user001", "password": "Pass@123"}
        """
        if not workflow:
            return LoginOutput(success=False, message="服务未初始化")

        try:
            result = await workflow.login_user(
                username=input.username,
                password=input.password,
                force_refresh=input.force_refresh,
            )
            return LoginOutput(
                success=result["success"],
                message=result["message"],
                token=result.get("token", ""),
            )
        except Exception as e:
            logger.error(f"登录失败: {e}")
            return LoginOutput(success=False, message=str(e))

    @mcp.tool()
    async def search_international_flights(
        input: SearchIntlFlightsInput,
    ) -> SearchIntlFlightsOutput:
        """
        查询国际机票（步骤 5）

        使用已登录的 Token，通过 /api/flight/intlsearch 查询国际航班列表。

        前置条件：
          - 已通过 login_user 完成登录

        支持单程和往返查询，可指定乘客数量和舱位等级。
        返回航班列表，包含 flightId、serialNumber、价格、舱位等信息，
        其中 flightId 和 serialNumber 用于后续下单。

        使用示例（北京→纽约单程）：
          {
            "from_city": "PEK",
            "to_city": "JFK",
            "from_date": "2026-06-01",
            "adult_count": 1
          }
        """
        if not workflow:
            return SearchIntlFlightsOutput(success=False, message="服务未初始化")

        try:
            result = await workflow.search_intl_flights(
                from_city=input.from_city,
                to_city=input.to_city,
                from_date=input.from_date,
                trip_type=input.trip_type,
                adult_count=input.adult_count,
                child_count=input.child_count,
                infant_count=input.infant_count,
                cabin=input.cabin,
                return_date=input.return_date,
            )
            return SearchIntlFlightsOutput(
                success=result["success"],
                message=result["message"],
                data=result.get("data"),
            )
        except Exception as e:
            logger.error(f"查询国际机票失败: {e}")
            return SearchIntlFlightsOutput(success=False, message=str(e))

    @mcp.tool()
    async def query_intl_ticket_rule(
        input: QueryIntlTicketRuleInput,
    ) -> GenericOutput:
        """
        查询国际机票退改签条款

        调用 /api/flight/queryIntlShoppingRule 接口，
        获取指定航班的退票、改签规则及费用。

        前置条件：
          - 已通过 login_user 完成登录
        """
        try:
            resp = await api_client.query_intl_ticket_rule(input.body)
            return GenericOutput(success=True, message="查询成功", data=resp)
        except Exception as e:
            logger.error(f"查询国际退改签条款失败: {e}")
            return GenericOutput(success=False, message=str(e))

    @mcp.tool()
    async def query_intl_order_detail(
        input: QueryIntlOrderDetailInput,
    ) -> GenericOutput:
        """
        查询国际机票订单详情

        调用 /api/flight/intldetail 接口，
        获取国际机票订单的详细信息，包括航班、乘客、价格等。

        前置条件：
          - 已通过 login_user 完成登录
        """
        try:
            resp = await api_client.query_intl_order_detail(input.body)
            return GenericOutput(success=True, message="查询成功", data=resp)
        except Exception as e:
            logger.error(f"查询国际机票订单详情失败: {e}")
            return GenericOutput(success=False, message=str(e))

    logger.info("航班工具注册完成（login_user / search_international_flights / query_intl_ticket_rule / query_intl_order_detail）")
