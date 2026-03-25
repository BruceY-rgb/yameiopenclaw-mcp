"""
出行人相关 MCP 工具（步骤 6）

提供以下能力：
  - 创建出行人（步骤 6）：POST /api/passenger/save
  - 查询出行人列表：POST /api/passenger/list
"""

import logging
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from fastmcp import FastMCP

from src.api.client import OntuotuApiClient
from src.workflow.orchestrator import WorkflowOrchestrator

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════
# 数据模型
# ═══════════════════════════════════════════════

class CreatePassengerInput(BaseModel):
    """创建出行人输入（步骤 6）"""
    name: str = Field(
        ...,
        description="乘客姓名（中文或英文）",
        examples=["张三", "ZHANG SAN"]
    )
    passenger_type: int = Field(
        default=0,
        description="乘客类型：0=成人，1=儿童，2=婴儿",
        ge=0,
        le=2
    )
    nationality: str = Field(
        ...,
        description="国籍二字码，如 CN（中国）、US（美国）、GB（英国）",
        pattern="^[A-Z]{2}$",
        examples=["CN", "US", "GB"]
    )
    id_type: str = Field(
        ...,
        description=(
            "证件类型：0=护照，1=其他，3=港澳通行证，"
            "4=回乡证，7=台湾通行证，8=台胞证，"
            "9=军人证，11=外国人永久居留身份证，"
            "14=海员证，15=外交人员证"
        ),
        pattern="^(0|1|3|4|7|8|9|11|14|15)$"
    )
    id_number: str = Field(
        ...,
        description="证件号码",
        examples=["E12345678"]
    )
    id_expiration: str = Field(
        ...,
        description="证件有效期，格式 yyyy-MM-dd",
        pattern="^\\d{4}-\\d{2}-\\d{2}$",
        examples=["2030-01-01"]
    )
    gender: int = Field(
        ...,
        description="性别：1=男，0=女",
        ge=0,
        le=1
    )
    birthday: str = Field(
        ...,
        description="出生日期，格式 yyyy-MM-dd",
        pattern="^\\d{4}-\\d{2}-\\d{2}$",
        examples=["1990-01-01"]
    )
    phone: Optional[str] = Field(
        None,
        description="手机号（可选）",
        examples=["13800138000"]
    )
    email: Optional[str] = Field(
        None,
        description="邮箱（可选）",
        examples=["example@email.com"]
    )


class CreatePassengerOutput(BaseModel):
    """创建出行人输出"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(default="", description="提示信息")
    passenger_id: str = Field(default="", description="出行人 ID（下单时使用）")
    data: Optional[Dict[str, Any]] = Field(None, description="出行人详情")


class ListPassengersInput(BaseModel):
    """查询出行人列表输入"""
    page_num: int = Field(default=1, description="页码", ge=1)
    page_size: int = Field(default=20, description="每页条数", ge=1, le=100)


class ListPassengersOutput(BaseModel):
    """查询出行人列表输出"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(default="", description="提示信息")
    data: Optional[Dict[str, Any]] = Field(None, description="出行人列表")


# ═══════════════════════════════════════════════
# 工具注册
# ═══════════════════════════════════════════════

def register_passenger_tools(
    mcp: FastMCP,
    api_client: OntuotuApiClient,
    workflow: Optional[WorkflowOrchestrator] = None,
):
    """注册出行人相关 MCP 工具"""

    @mcp.tool()
    async def create_passenger(input: CreatePassengerInput) -> CreatePassengerOutput:
        """
        创建出行人（步骤 6）

        调用 /api/passenger/save 接口，添加乘客信息。
        创建成功后返回 passenger_id，用于步骤 7（国际机票下单）。

        前置条件：
          - 已通过 login_user 完成登录

        使用示例：
          {
            "name": "张三",
            "passenger_type": 0,
            "nationality": "CN",
            "id_type": "0",
            "id_number": "E12345678",
            "id_expiration": "2030-01-01",
            "gender": 1,
            "birthday": "1990-01-01",
            "phone": "13800138000"
          }
        """
        if not workflow:
            return CreatePassengerOutput(success=False, message="服务未初始化")

        try:
            result = await workflow.create_passenger(
                name=input.name,
                passenger_type=input.passenger_type,
                nationality=input.nationality,
                id_type=input.id_type,
                id_number=input.id_number,
                id_expiration=input.id_expiration,
                gender=input.gender,
                birthday=input.birthday,
                phone=input.phone,
                email=input.email,
            )
            return CreatePassengerOutput(
                success=result["success"],
                message=result["message"],
                passenger_id=result.get("passenger_id", ""),
                data=result.get("data"),
            )
        except Exception as e:
            logger.error(f"创建出行人失败: {e}")
            return CreatePassengerOutput(success=False, message=str(e))

    @mcp.tool()
    async def list_passengers(input: ListPassengersInput) -> ListPassengersOutput:
        """
        查询出行人列表

        调用 /api/passenger/list 接口，获取当前账号下所有出行人。

        前置条件：
          - 已通过 login_user 完成登录
        """
        try:
            resp = await api_client.list_passengers(
                {"pageNum": input.page_num, "pageSize": input.page_size}
            )
            return ListPassengersOutput(
                success=True,
                message="查询成功",
                data=resp,
            )
        except Exception as e:
            logger.error(f"查询出行人列表失败: {e}")
            return ListPassengersOutput(success=False, message=str(e))

    logger.info("出行人工具注册完成（create_passenger / list_passengers）")
