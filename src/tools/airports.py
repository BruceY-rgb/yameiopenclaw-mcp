"""
机场数据 MCP 工具

提供以下能力：
  - 城市→机场代码转换
  - 机场代码验证
  - 机场搜索（支持中文/英文）
  - 数据统计分析
"""

import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from fastmcp import FastMCP

from src.data.airports import AirportLoader, get_airport_loader

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════
# 数据模型
# ═══════════════════════════════════════════════

class CityToAirportInput(BaseModel):
    """城市转机场输入"""
    city: str = Field(..., description="城市名称，如：北京、上海、东京、洛杉矶")


class AirportCodeInput(BaseModel):
    """机场代码验证输入"""
    code: str = Field(..., description="机场三字码，如：PEK、LAX、NRT")


class AirportSearchInput(BaseModel):
    """机场搜索输入"""
    keyword: str = Field(..., description="搜索关键词（城市名、机场名、英文名、代码）")
    limit: int = Field(default=10, description="返回结果数量限制")


class AirportStatsInput(BaseModel):
    """机场统计输入（无参数）"""
    pass


class AirportOutput(BaseModel):
    """机场信息输出"""
    code: str = Field(..., description="机场代码")
    name: str = Field(..., description="机场全称")
    city: str = Field(..., description="所属城市")
    city_code: str = Field(..., description="城市三字码")
    country: str = Field(..., description="所属国家/地区")
    is_customs: bool = Field(..., description="是否海关机场")


class CityToAirportOutput(BaseModel):
    """城市转机场输出"""
    success: bool = Field(..., description="是否成功")
    city: str = Field(..., description="城市名称")
    city_code: Optional[str] = Field(None, description="城市三字码")
    airports: List[AirportOutput] = Field(default_factory=list, description="机场列表")


class AirportSearchOutput(BaseModel):
    """机场搜索输出"""
    success: bool = Field(..., description="是否成功")
    total: int = Field(..., description="结果总数")
    airports: List[AirportOutput] = Field(default_factory=list, description="机场列表")


class AirportStatsOutput(BaseModel):
    """机场统计输出"""
    success: bool = Field(..., description="是否成功")
    total: int = Field(..., description="机场总数")
    customs: int = Field(..., description="海关机场数量")
    non_customs: int = Field(..., description="非海关机场数量")
    countries: int = Field(..., description="国家/地区数量")
    cities: int = Field(..., description="城市数量")
    top_countries: Dict[str, int] = Field(default_factory=dict, description="各国机场数量 Top20")
    top_cities: Dict[str, int] = Field(default_factory=dict, description="各城市机场数量 Top20")


class ValidationOutput(BaseModel):
    """验证结果输出"""
    valid: bool = Field(..., description="是否有效")
    message: str = Field(..., description="提示信息")
    airport: Optional[AirportOutput] = Field(None, description="机场信息（有效时返回）")


# ═══════════════════════════════════════════════
# 工具注册
# ═══════════════════════════════════════════════

def register_airport_tools(mcp: FastMCP):
    """注册机场数据 MCP 工具"""

    @mcp.tool()
    async def city_to_airports(input: CityToAirportInput) -> CityToAirportOutput:
        """
        城市→机场转换

        根据城市名称查询对应的机场代码列表。
        支持中文城市名，如"北京"→[PEK, PKX]，"上海"→[PVG, SHA]。

        使用示例：
          {"city": "北京"}
          {"city": "东京"}
          {"city": "洛杉矶"}
        """
        loader = get_airport_loader()
        airports = loader.get_by_city(input.city)

        if not airports:
            return CityToAirportOutput(
                success=False,
                city=input.city,
                city_code=None,
                airports=[],
            )

        city_code = airports[0].get("city_code")
        airport_outputs = [
            AirportOutput(
                code=a.get("code", ""),
                name=a.get("name", ""),
                city=a.get("city", ""),
                city_code=a.get("city_code", ""),
                country=a.get("country", ""),
                is_customs=a.get("is_customs", False),
            )
            for a in airports
        ]

        return CityToAirportOutput(
            success=True,
            city=input.city,
            city_code=city_code,
            airports=airport_outputs,
        )

    @mcp.tool()
    async def validate_airport_code(input: AirportCodeInput) -> ValidationOutput:
        """
        验证机场代码

        校验机场三字码是否有效，返回机场详细信息。

        使用示例：
          {"code": "PEK"}
          {"code": "LAX"}
          {"code": "NRT"}
        """
        loader = get_airport_loader()
        airport = loader.get_by_code(input.code)

        if not airport:
            return ValidationOutput(
                valid=False,
                message=f"无效的机场代码: {input.code}",
                airport=None,
            )

        return ValidationOutput(
            valid=True,
            message=f"有效的机场代码: {airport.get('name', '')}",
            airport=AirportOutput(
                code=airport.get("code", ""),
                name=airport.get("name", ""),
                city=airport.get("city", ""),
                city_code=airport.get("city_code", ""),
                country=airport.get("country", ""),
                is_customs=airport.get("is_customs", False),
            ),
        )

    @mcp.tool()
    async def search_airports(input: AirportSearchInput) -> AirportSearchOutput:
        """
        搜索机场

        根据关键词搜索机场，支持城市名、机场名、英文名、代码模糊匹配。

        使用示例：
          {"keyword": "北京", "limit": 5}
          {"keyword": "Shanghai", "limit": 10}
          {"keyword": "LAX", "limit": 3}
        """
        loader = get_airport_loader()
        results = loader.search(input.keyword)[:input.limit]

        airport_outputs = [
            AirportOutput(
                code=a.get("code", ""),
                name=a.get("name", ""),
                city=a.get("city", ""),
                city_code=a.get("city_code", ""),
                country=a.get("country", ""),
                is_customs=a.get("is_customs", False),
            )
            for a in results
        ]

        return AirportSearchOutput(
            success=True,
            total=len(results),
            airports=airport_outputs,
        )

    @mcp.tool()
    async def get_airport_statistics(input: AirportStatsInput) -> AirportStatsOutput:
        """
        机场数据统计

        获取机场数据的统计信息，包括总数、各国/城市分布等。

        使用示例：
          {}
        """
        loader = get_airport_loader()
        stats = loader.get_stats()

        return AirportStatsOutput(
            success=True,
            total=stats.get("total", 0),
            customs=stats.get("customs", 0),
            non_customs=stats.get("non_customs", 0),
            countries=stats.get("countries", 0),
            cities=stats.get("cities", 0),
            top_countries=stats.get("top_countries", {}),
            top_cities=stats.get("top_cities", {}),
        )

    logger.info("机场工具注册完成（city_to_airports / validate_airport_code / search_airports / get_airport_statistics）")