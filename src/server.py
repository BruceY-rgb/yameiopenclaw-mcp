#!/usr/bin/env python3
"""
美亚航旅API MCP Server

提供国际机票查询、预订、支付等功能的MCP Server。
使用FastMCP框架实现，支持stdio和HTTP传输模式。
"""

import os
import sys
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastmcp import FastMCP
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """应用配置"""
    model_config = SettingsConfigDict(
        env_prefix="",
        case_sensitive=False
    )

    # API配置
    meiya_api_url: str = "https://api.meiya.com"
    meiya_username: str = ""
    meiya_password: str = ""

    # MCP配置
    mcp_transport: str = "stdio"
    mcp_port: int = 8000

    # 日志配置
    log_level: str = "INFO"

    # 请求配置
    request_timeout: float = 30.0
    max_retries: int = 3


settings = Settings()


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[dict]:
    """应用生命周期管理

    在服务启动时初始化各个组件，在服务关闭时清理资源。
    """
    # 启动时初始化
    logger.info("正在初始化美亚航旅MCP Server...")

    # 检查必需的配置
    if not settings.meiya_username or not settings.meiya_password:
        logger.warning("MEIYA_USERNAME 或 MEIYA_PASSWORD 未设置，部分功能可能不可用")

    # 导入组件
    from src.api.client import MeiyaApiClient
    from src.auth.manager import AuthManager
    from src.workflow.orchestrator import WorkflowOrchestrator
    from src.tools.flights import register_flight_tools
    from src.tools.passengers import register_passenger_tools
    from src.tools.orders import register_order_tools

    # 创建API客户端
    api_client = MeiyaApiClient(
        base_url=settings.meiya_api_url,
        username=settings.meiya_username,
        password=settings.meiya_password,
        timeout=settings.request_timeout,
        max_retries=settings.max_retries
    )

    # 创建认证管理器
    auth_manager = AuthManager(api_client)

    # 创建工作流编排器
    workflow = WorkflowOrchestrator(api_client, auth_manager)

    # 注册工具
    register_flight_tools(server, api_client, workflow)
    register_passenger_tools(server, api_client, workflow)
    register_order_tools(server, api_client, workflow)

    logger.info("美亚航旅MCP Server初始化完成")
    logger.info(f"传输模式: {settings.mcp_transport}")
    logger.info(f"API地址: {settings.meiya_api_url}")

    yield {
        "api_client": api_client,
        "auth_manager": auth_manager,
        "workflow": workflow
    }

    # 关闭时清理
    logger.info("正在关闭美亚航旅MCP Server...")
    await api_client.close()
    logger.info("美亚航旅MCP Server已关闭")


# 创建MCP Server
mcp = FastMCP(
    "美亚航旅API",
    lifespan=app_lifespan
)


def main():
    """主入口函数"""
    # 获取传输模式
    transport = os.getenv("MCP_TRANSPORT", settings.mcp_transport)
    port = int(os.getenv("MCP_PORT", settings.mcp_port))

    logger.info(f"启动MCP Server，传输模式: {transport}")

    try:
        if transport == "stdio":
            # 标准输入输出模式（适合Claude Desktop）
            mcp.run(transport="stdio")
        elif transport == "http":
            # HTTP模式（适合远程部署）
            mcp.run(transport="streamable-http", host="0.0.0.0", port=port)
        elif transport == "sse":
            # SSE模式（适合实时推送）
            mcp.run(transport="sse", host="0.0.0.0", port=port)
        else:
            logger.error(f"不支持的传输模式: {transport}")
            sys.exit(1)
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在关闭...")
    except Exception as e:
        logger.error(f"Server错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
