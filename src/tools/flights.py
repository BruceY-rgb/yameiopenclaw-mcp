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
    # 解析后的航班数据
    flights: Optional[List[Dict[str, Any]]] = Field(None, description="航班列表")
    total: Optional[int] = Field(None, description="航班总数")
    serial_number: Optional[str] = Field(None, description="查询序列号")
    # 原始数据（保留备查）
    data: Optional[Dict[str, Any]] = Field(None, description="原始查询结果")


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

            # 解析响应数据
            api_data = result.get("data", {})
            code = api_data.get("code", "")
            description = api_data.get("description", "")

            # 检查API返回状态
            if code != "000000":
                return SearchIntlFlightsOutput(
                    success=False,
                    message=description or f"API返回错误: {code}"
                )

            # 从 detail.flightDetailList 获取航班数据
            detail = api_data.get("detail", {})
            flight_list = detail.get("flightDetailList", [])
            serial_number = detail.get("serialNumber", "")

            # 提取关键字段
            parsed_flights = []
            for f in flight_list:
                # 解析航班信息
                finance = f.get("financeDetail", {})
                finance_list = finance.get("financeList", [{}])
                first_finance = finance_list[0] if finance_list else {}

                # 获取价格信息
                sale_price = first_finance.get("salePrice", "N/A")
                tax = first_finance.get("tax", "0")
                service_fee = first_finance.get("serviceFee", "0")
                total_price = float(sale_price) + float(tax) + float(service_fee) if sale_price != "N/A" else "N/A"

                # 获取航司信息
                airline_cn = f.get("airlineCN", "")
                airline_en = f.get("airlineEN", "")
                airline_code = f.get("airline", "")

                # 从 brand 获取舱位等级名称
                brand = first_finance.get("brand", [{}])[0] if first_finance.get("brand") else {}
                cabin_brand_name = brand.get("brandNameCh", "") or brand.get("brandName", "")
                cabin_class_code = brand.get("brandCode", "")

                # 从 tripList 获取航段信息
                trip_list = f.get("tripList", [])
                segments = []
                total_duration_minutes = 0
                for trip in trip_list:
                    for flight in trip.get("flightList", []):
                        # 解析飞行时长
                        duration = flight.get("duration", "00:00")
                        parts = duration.split(":")
                        if len(parts) == 2:
                            total_duration_minutes += int(parts[0]) * 60 + int(parts[1])

                        segments.append({
                            "flight_no": flight.get("flightNo", ""),
                            "airline": flight.get("airline", ""),
                            "airline_name": flight.get("airlineName", ""),
                            "dep_airport": flight.get("departureAirportCode", ""),
                            "dep_airport_name": flight.get("departureAirportName", ""),
                            "dep_city_name": flight.get("departureCityName", ""),
                            "dep_city_code": flight.get("departureCityCode", ""),
                            "arr_airport": flight.get("destinationAirportCode", ""),
                            "arr_airport_name": flight.get("destinationAirportName", ""),
                            "arr_city_name": flight.get("destinationCityName", ""),
                            "arr_city_code": flight.get("destinationCityCode", ""),
                            "dep_time": flight.get("departureDateTime", ""),
                            "arr_time": flight.get("arrivalDateTime", ""),
                            "duration": duration,
                            "cabin_type": flight.get("cabinType", ""),
                            "class_no": flight.get("classNo", ""),
                        })

                # 计算总飞行时长
                hours = total_duration_minutes // 60
                minutes = total_duration_minutes % 60
                total_duration = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"

                parsed_flights.append({
                    "airline_cn": airline_cn,
                    "airline_en": airline_en,
                    "airline_code": airline_code,
                    "sale_price": sale_price,
                    "tax": tax,
                    "service_fee": service_fee,
                    "total_price": str(total_price) if isinstance(total_price, float) else total_price,
                    "currency": detail.get("payCurrency", "CNY"),
                    "cabin_class": f.get("cabinClass", ""),
                    "cabin_type": f.get("cabinType", ""),
                    "cabin_name": f.get("cabinName", ""),
                    "cabin_brand_name": cabin_brand_name,  # 舱位等级名称
                    "cabin_brand_code": cabin_class_code,
                    "total_duration": total_duration,  # 总飞行时长
                    "stop_count": len(segments) - 1 if len(segments) > 0 else 0,  # 经停次数
                    # 保留原始数据供进一步查询
                    "flight_id": f.get("flightID", ""),
                    "fare_key": f.get("fareKey", ""),
                    "segments": segments,  # 航段信息
                    "trip_list": trip_list,  # 完整行程
                })

            return SearchIntlFlightsOutput(
                success=True,
                message=f"查询成功，共 {len(parsed_flights)} 个航班",
                flights=parsed_flights,
                total=len(parsed_flights),
                serial_number=serial_number,
                data=api_data,  # 保留原始数据
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
