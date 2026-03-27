#!/usr/bin/env python3
"""
腾云商旅 MCP Server（小龙虾 openclaw）

通过调用 https://sla.ontuotu.com 的 Java 后端接口，
为 AI 助手提供国际机票查询、出行人管理、机票下单等能力。

业务流程：
  1. 运营后台创建公司，分配 AppKey / AppSecret
  2. 小龙虾配置公司 AppKey / AppSecret（环境变量）
  3. 小龙虾使用公司密钥调用开放接口，创建用户账号密码
  4. 小龙虾使用用户账号密码调用登录接口，获取 Token
  5. 小龙虾使用 Token 查询国际机票分页
  6. 小龙虾使用 Token 创建出行人
  7. 小龙虾使用 Token 国际机票下单
"""

import os
import sys
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastmcp import FastMCP
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """应用配置

    必须在环境变量（或 .env 文件）中设置：
      ONTUOTU_APP_KEY      公司 AppKey（运营后台创建公司后获取）
      ONTUOTU_APP_SECRET   公司 AppSecret（运营后台创建公司后获取）

    可选配置：
      ONTUOTU_BASE_URL     API 基础地址（默认 https://sla.ontuotu.com）
      MCP_TRANSPORT        传输模式：stdio / http / sse（默认 stdio）
      MCP_PORT             HTTP 模式监听端口（默认 8000）
      REQUEST_TIMEOUT      请求超时秒数（默认 30）
      MAX_RETRIES          最大重试次数（默认 3）
    """

    model_config = SettingsConfigDict(env_prefix="", case_sensitive=False)

    # 公司密钥（必填）
    ontuotu_app_key: str = ""
    ontuotu_app_secret: str = ""

    # API 地址
    ontuotu_base_url: str = "https://sla.ontuotu.com"

    # MCP 配置
    mcp_transport: str = "stdio"
    mcp_port: int = 8000

    # 请求配置
    request_timeout: float = 30.0
    max_retries: int = 3


settings = Settings()


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[dict]:
    """应用生命周期管理"""
    logger.info("正在初始化腾云商旅 MCP Server（小龙虾）...")

    if not settings.ontuotu_app_key or not settings.ontuotu_app_secret:
        logger.warning(
            "ONTUOTU_APP_KEY 或 ONTUOTU_APP_SECRET 未设置，"
            "创建用户账号功能将不可用"
        )

    from src.api.client import OntuotuApiClient
    from src.auth.manager import AuthManager
    from src.workflow.orchestrator import WorkflowOrchestrator
    from src.tools.flights import register_flight_tools
    from src.tools.passengers import register_passenger_tools
    from src.tools.orders import register_order_tools

    # 创建 API 客户端
    api_client = OntuotuApiClient(
        app_key=settings.ontuotu_app_key,
        app_secret=settings.ontuotu_app_secret,
        base_url=settings.ontuotu_base_url,
        timeout=settings.request_timeout,
        max_retries=settings.max_retries,
    )

    # 创建认证管理器
    auth_manager = AuthManager(api_client)

    # 创建工作流编排器
    workflow = WorkflowOrchestrator(api_client, auth_manager)

    # 注册 MCP 工具
    register_flight_tools(server, api_client, workflow)
    register_passenger_tools(server, api_client, workflow)
    register_order_tools(server, api_client, workflow)

    logger.info("腾云商旅 MCP Server 初始化完成")
    logger.info(f"传输模式: {settings.mcp_transport}")
    logger.info(f"API 地址: {settings.ontuotu_base_url}")

    yield {
        "api_client": api_client,
        "auth_manager": auth_manager,
        "workflow": workflow,
    }

    logger.info("正在关闭腾云商旅 MCP Server...")
    await api_client.close()
    logger.info("腾云商旅 MCP Server 已关闭")


# 创建 MCP Server 实例
mcp = FastMCP(
    "腾云商旅 API（小龙虾）",
    lifespan=app_lifespan,
)


def main():
    """主入口"""
    transport = os.getenv("MCP_TRANSPORT", settings.mcp_transport)
    port = int(os.getenv("MCP_PORT", settings.mcp_port))

    logger.info(f"启动 MCP Server，传输模式: {transport}")

    try:
        if transport == "stdio":
            mcp.run(transport="stdio")
        elif transport == "http":
            mcp.run(transport="http", host="0.0.0.0", port=port)
        elif transport == "sse":
            mcp.run(transport="sse", host="0.0.0.0", port=port)
        else:
            logger.error(f"不支持的传输模式: {transport}")
            sys.exit(1)
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在关闭...")
    except Exception as e:
        logger.error(f"Server 错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
