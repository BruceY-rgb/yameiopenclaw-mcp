"""
出行人相关MCP工具

提供出行人创建、更新、查询等功能。
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

class CreatePassengerInput(BaseModel):
    """创建出行人输入"""
    name: str = Field(
        ...,
        description="乘客姓名（中文或英文）",
        examples=["张三", "John Smith"]
    )
    passenger_type: str = Field(
        default="adult",
        description="乘客类型: adult（成人）/ child（儿童）/ infant（婴儿）",
        pattern="^(adult|child|infant)$"
    )
    nationality: str = Field(
        ...,
        description="国籍二字代码，如CN（中国）、US（美国）、GB（英国）",
        pattern="^[A-Z]{2}$",
        examples=["CN", "US", "GB", "JP"]
    )
    id_type: str = Field(
        ...,
        description="""证件类型代码:
        0=护照, 1=其他, 3=港澳通行证,
        4=回乡证, 7=台湾通行证, 8=台胞证,
        9=军人证, 11=外国人永久居留身份证,
        14=海员证, 15=外交人员证""",
        pattern="^(0|1|3|4|7|8|9|11|14|15)$"
    )
    id_number: str = Field(
        ...,
        description="证件号码",
        examples=["E12345678", "H1234567890"]
    )
    id_nationality: Optional[str] = Field(
        None,
        description="证件签发国二字码（默认与国籍相同）",
        pattern="^[A-Z]{2}$"
    )
    id_expiration: str = Field(
        ...,
        description="证件有效期，格式YYYY-MM-DD",
        pattern="^\\d{4}-\\d{2}-\\d{2}$",
        examples=["2030-01-01"]
    )
    gender: str = Field(
        ...,
        description="性别: 1（男）/ 0（女）",
        pattern="^[01]$"
    )
    birthday: str = Field(
        ...,
        description="出生日期，格式YYYY-MM-DD",
        pattern="^\\d{4}-\\d{2}-\\d{2}$",
        examples=["1990-01-01"]
    )
    phone_number: Optional[str] = Field(
        None,
        description="手机号",
        examples=["13800138000"]
    )
    email: Optional[str] = Field(
        None,
        description="邮箱",
        examples=["example@email.com"]
    )


class CreatePassengerOutput(BaseModel):
    """创建出行人输出"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(default="", description="提示信息")
    passenger_id: Optional[str] = Field(None, description="出行人ID")
    data: Optional[dict] = Field(None, description="出行人详情")


class UpdatePassengerInput(BaseModel):
    """更新出行人输入"""
    passenger_id: str = Field(..., description="出行人ID")
    name: Optional[str] = Field(None, description="乘客姓名")
    phone_number: Optional[str] = Field(None, description="手机号")
    email: Optional[str] = Field(None, description="邮箱")
    id_expiration: Optional[str] = Field(
        None,
        description="证件有效期，格式YYYY-MM-DD",
        pattern="^\\d{4}-\\d{2}-\\d{2}$"
    )


class UpdatePassengerOutput(BaseModel):
    """更新出行人输出"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(default="", description="提示信息")
    data: Optional[dict] = Field(None, description="更新后的出行人详情")


class GetPassengerInput(BaseModel):
    """获取出行人输入"""
    passenger_id: str = Field(..., description="出行人ID")


class GetPassengerOutput(BaseModel):
    """获取出行人输出"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(default="", description="提示信息")
    data: Optional[dict] = Field(None, description="出行人详情")


# ===========================================
# 工具注册函数
# ===========================================

def register_passenger_tools(
    mcp: FastMCP,
    api_client: MeiyaApiClient,
    workflow: Optional[WorkflowOrchestrator] = None
):
    """注册出行人相关工具"""

    @mcp.tool()
    async def create_passenger(input: CreatePassengerInput) -> CreatePassengerOutput:
        """
        创建出行人

        添加乘客信息（姓名、证件、联系方式），用于预订机票。
        支持成人、儿童和婴儿。

        注意：
        - 婴儿必须有对应的成人陪同
        - 儿童和成人价格不同
        - 证件信息必须准确，否则无法出票

        Args:
            name: 乘客姓名（中文或英文）
            passenger_type: 乘客类型
            nationality: 国籍
            id_type: 证件类型
            id_number: 证件号码
            id_expiration: 证件有效期
            gender: 性别
            birthday: 出生日期
            phone_number: 手机号（可选）
            email: 邮箱（可选）

        使用示例:
        {
            "name": "张三",
            "passenger_type": "adult",
            "nationality": "CN",
            "id_type": "0",
            "id_number": "E12345678",
            "id_expiration": "2030-01-01",
            "gender": "1",
            "birthday": "1990-01-01",
            "phone_number": "13800138000",
            "email": "zhangsan@example.com"
        }
        """
        try:
            logger.info(f"创建出行人: name={input.name}, type={input.passenger_type}")

            # 构建请求数据
            passenger_data = {
                "name": input.name,
                "passengerType": input.passenger_type,
                "nationality": input.nationality,
                "idType": input.id_type,
                "idNumber": input.id_number,
                "idExpiration": input.id_expiration,
                "gender": input.gender,
                "birthday": input.birthday
            }

            # 可选字段
            if input.id_nationality:
                passenger_data["idNationality"] = input.id_nationality
            if input.phone_number:
                passenger_data["phoneNumber"] = input.phone_number
            if input.email:
                passenger_data["email"] = input.email

            response = await api_client.create_passenger(passenger_data)

            data = response.get("data", {})
            passenger_id = data.get("passengerId")

            logger.info(f"创建出行人成功: passenger_id={passenger_id}")

            return CreatePassengerOutput(
                success=True,
                message="创建成功",
                passenger_id=passenger_id,
                data=data
            )

        except Exception as e:
            logger.error(f"创建出行人失败: {e}")
            return CreatePassengerOutput(
                success=False,
                message=f"创建失败: {str(e)}"
            )

    @mcp.tool()
    async def update_passenger(input: UpdatePassengerInput) -> UpdatePassengerOutput:
        """
        更新出行人信息

        修改出行人的联系方式、证件有效期等信息。

        Args:
            passenger_id: 出行人ID
            name: 乘客姓名（可选）
            phone_number: 手机号（可选）
            email: 邮箱（可选）
            id_expiration: 证件有效期（可选）

        Returns:
            更新结果
        """
        try:
            logger.info(f"更新出行人: passenger_id={input.passenger_id}")

            # 构建更新数据
            update_data = {}
            if input.name:
                update_data["name"] = input.name
            if input.phone_number:
                update_data["phoneNumber"] = input.phone_number
            if input.email:
                update_data["email"] = input.email
            if input.id_expiration:
                update_data["idExpiration"] = input.id_expiration

            response = await api_client.update_passenger(
                input.passenger_id,
                update_data
            )

            logger.info(f"更新出行人成功: passenger_id={input.passenger_id}")

            return UpdatePassengerOutput(
                success=True,
                message="更新成功",
                data=response.get("data", {})
            )

        except Exception as e:
            logger.error(f"更新出行人失败: {e}")
            return UpdatePassengerOutput(
                success=False,
                message=f"更新失败: {str(e)}"
            )

    @mcp.tool()
    async def get_passenger(input: GetPassengerInput) -> GetPassengerOutput:
        """
        获取出行人信息

        根据出行人ID获取详细信息。

        Args:
            passenger_id: 出行人ID

        Returns:
            出行人详细信息
        """
        try:
            logger.info(f"获取出行人: passenger_id={input.passenger_id}")

            response = await api_client.get_passenger(input.passenger_id)

            return GetPassengerOutput(
                success=True,
                message="获取成功",
                data=response.get("data", {})
            )

        except Exception as e:
            logger.error(f"获取出行人失败: {e}")
            return GetPassengerOutput(
                success=False,
                message=f"获取失败: {str(e)}"
            )

    logger.info("出行人工具注册完成")
