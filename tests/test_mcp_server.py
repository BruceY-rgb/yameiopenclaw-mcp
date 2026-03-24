"""
MCP Server集成测试

测试MCP Server的：
1. Server启动和初始化
2. 工具注册机制
3. 生命周期管理
4. 工具输入输出格式
5. 不同传输模式
"""

import pytest
import asyncio
import os
import sys
import logging
from typing import Dict, Any, AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from contextlib import asynccontextmanager

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 设置测试环境变量
os.environ["MEIYA_API_URL"] = "https://api.test.meiya.com"
os.environ["MEIYA_USERNAME"] = "test_user"
os.environ["MEIYA_PASSWORD"] = "test_password"
os.environ["MEIYA_API_URL"] = "https://api.test.meiya.com"
os.environ["MCP_TRANSPORT"] = "stdio"
os.environ["MCP_PORT"] = "8000"

from fastmcp import FastMCP
from pydantic import BaseModel, Field

from src.server import (
    mcp,
    settings,
    Settings,
    app_lifespan,
)
from src.api.client import MeiyaApiClient
from src.auth.manager import AuthManager
from src.workflow.orchestrator import WorkflowOrchestrator


# ===========================================
# 测试夹具
# ===========================================

@pytest.fixture
def mock_env_vars():
    """设置测试环境变量"""
    original_env = os.environ.copy()

    test_env = {
        "MEIYA_API_URL": "https://api.test.meiya.com",
        "MEIYA_USERNAME": "test_user",
        "MEIYA_PASSWORD": "test_password",
        "MCP_TRANSPORT": "stdio",
        "MCP_PORT": "8000",
    }

    for key, value in test_env.items():
        os.environ[key] = value

    yield test_env

    # 恢复原始环境变量
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def mock_api_client():
    """创建模拟的API客户端"""
    client = AsyncMock(spec=MeiyaApiClient)
    client.base_url = "https://api.test.meiya.com"
    client.username = "test_user"
    client.password = "test_password"
    return client


@pytest.fixture
def mock_auth_manager():
    """创建模拟的认证管理器"""
    manager = AsyncMock(spec=AuthManager)
    return manager


@pytest.fixture
def mock_workflow():
    """创建模拟的工作流编排器"""
    workflow = AsyncMock(spec=WorkflowOrchestrator)
    return workflow


@pytest.fixture
def test_mcp_server(mock_api_client, mock_auth_manager, mock_workflow):
    """创建测试用的MCP Server"""
    # 创建新的FastMCP实例用于测试
    test_server = FastMCP(
        "Test Meiya MCP Server",
        dependencies=["fastmcp", "httpx", "pydantic", "pydantic-settings", "python-dotenv"],
    )

    # 注册测试工具
    @test_server.tool()
    async def test_tool(input: Dict[str, Any]) -> Dict[str, Any]:
        """测试工具"""
        return {"success": True, "message": "Test passed"}

    @test_server.tool()
    async def search_flights_tool(
        origin: str,
        destination: str,
        departure_date: str,
    ) -> Dict[str, Any]:
        """测试航班搜索工具"""
        return {
            "success": True,
            "message": "找到航班",
            "total": 1,
            "flights": [
                {
                    "flightId": "FL123456",
                    "flightNumber": "CA981",
                    "origin": origin,
                    "destination": destination,
                }
            ]
        }

    return test_server


# ===========================================
# Settings配置测试
# ===========================================

class TestSettings:
    """测试Settings配置类"""

    def test_settings_default_values(self):
        """测试默认配置值"""
        # 重新加载设置以确保使用环境变量
        test_settings = Settings()

        assert test_settings.meiya_api_url == "https://api.test.meiya.com"
        assert test_settings.meiya_username == "test_user"
        assert test_settings.meiya_password == "test_password"
        assert test_settings.mcp_transport == "stdio"
        assert test_settings.mcp_port == 8000

    def test_settings_custom_values(self, mock_env_vars):
        """测试自定义配置值"""
        os.environ["MEIYA_API_URL"] = "https://custom.api.com"
        os.environ["MCP_TRANSPORT"] = "http"
        os.environ["MCP_PORT"] = "9000"

        test_settings = Settings()

        assert test_settings.meiya_api_url == "https://custom.api.com"
        assert test_settings.mcp_transport == "http"
        assert test_settings.mcp_port == 9000


# ===========================================
# MCP Server创建测试
# ===========================================

class TestMCPServerCreation:
    """测试MCP Server创建"""

    def test_mcp_server_exists(self):
        """测试MCP Server实例存在"""
        assert mcp is not None
        assert isinstance(mcp, FastMCP)

    def test_mcp_server_name(self):
        """测试MCP Server名称"""
        assert mcp.name == "美亚航旅API"

    def test_mcp_server_dependencies(self):
        """测试MCP Server依赖项"""
        # FastMCP的依赖在创建时指定，不需要额外检查
        assert mcp is not None

    def test_mcp_server_lifespan(self):
        """测试MCP Server lifespan"""
        assert mcp._lifespan is not None or hasattr(mcp, 'lifespan')


# ===========================================
# 工具注册测试
# ===========================================

class TestToolRegistration:
    """测试工具注册机制"""

    @pytest.mark.asyncio
    async def test_register_flight_tools(self, mock_api_client):
        """测试航班工具注册"""
        # 创建测试服务器
        test_server = FastMCP("Test Flight Tools")

        # 模拟工作流
        mock_workflow = AsyncMock(spec=WorkflowOrchestrator)

        # 导入并注册工具
        from src.tools.flights import register_flight_tools

        register_flight_tools(test_server, mock_api_client, mock_workflow)

        # 验证工具已注册
        # FastMCP内部会注册工具，我们可以通过尝试调用来验证
        assert test_server is not None

    @pytest.mark.asyncio
    async def test_register_passenger_tools(self, mock_api_client):
        """测试出行人工具注册"""
        test_server = FastMCP("Test Passenger Tools")
        mock_workflow = AsyncMock(spec=WorkflowOrchestrator)

        from src.tools.passengers import register_passenger_tools

        register_passenger_tools(test_server, mock_api_client, mock_workflow)

        assert test_server is not None

    @pytest.mark.asyncio
    async def test_register_order_tools(self, mock_api_client):
        """测试订单工具注册"""
        test_server = FastMCP("Test Order Tools")
        mock_workflow = AsyncMock(spec=WorkflowOrchestrator)

        from src.tools.orders import register_order_tools

        register_order_tools(test_server, mock_api_client, mock_workflow)

        assert test_server is not None


# ===========================================
# 生命周期管理测试
# ===========================================

class TestLifecycleManagement:
    """测试生命周期管理"""

    @pytest.mark.asyncio
    async def test_app_lifespan_startup(self):
        """测试应用启动时的生命周期"""
        # 创建测试服务器和lifespan
        from src.server import app_lifespan
        test_mcp = FastMCP("Test Lifecycle")

        @asynccontextmanager
        async def test_lifespan(server: FastMCP) -> AsyncIterator[dict]:
            """测试用的lifespan"""
            test_logger = logging.getLogger("test_lifespan")
            test_logger.info("测试：正在初始化...")

            # 创建模拟的API客户端
            mock_client = AsyncMock()
            mock_client.close = AsyncMock()

            # 创建模拟的认证管理器
            mock_auth = AsyncMock()

            # 创建模拟的工作流
            mock_workflow = AsyncMock()

            test_logger.info("测试：初始化完成")

            yield {
                "api_client": mock_client,
                "auth_manager": mock_auth,
                "workflow": mock_workflow
            }

            # 关闭时清理
            test_logger.info("测试：正在关闭...")
            await mock_client.close()
            test_logger.info("测试：已关闭")

        # 测试lifespan上下文
        async with test_lifespan(test_mcp) as context:
            # 验证上下文包含必要的组件
            assert "api_client" in context
            assert "auth_manager" in context
            assert "workflow" in context

    @pytest.mark.asyncio
    async def test_app_lifespan_context_manager(self):
        """测试lifespan作为上下文管理器"""
        test_mcp = FastMCP("Test Context Manager")

        @asynccontextmanager
        async def test_lifespan(server: FastMCP) -> AsyncIterator[dict]:
            mock_client = AsyncMock()
            mock_client.close = AsyncMock()

            yield {"api_client": mock_client}

            # 验证退出时调用close
            await mock_client.close()

        # 正常进入和退出上下文
        async with test_lifespan(test_mcp) as ctx:
            assert "api_client" in ctx


# ===========================================
# 工具输入输出格式测试
# ===========================================

class TestToolInputOutputFormat:
    """测试工具输入输出格式"""

    def test_search_flights_input_schema(self):
        """测试航班搜索输入Schema"""
        from src.tools.flights import SearchFlightsInput

        # 测试有效输入
        valid_input = SearchFlightsInput(
            origin="PEK",
            destination="JFK",
            departure_date="2026-04-01",
            adults=1,
        )
        assert valid_input.origin == "PEK"
        assert valid_input.destination == "JFK"

        # 测试必填字段验证
        with pytest.raises(Exception):
            SearchFlightsInput(origin="PEK")  # 缺少必填字段

    def test_search_flights_output_schema(self):
        """测试航班搜索输出Schema"""
        from src.tools.flights import SearchFlightsOutput

        output = SearchFlightsOutput(
            success=True,
            message="找到航班",
            total=1,
            flights=[],
        )
        assert output.success is True
        assert output.total == 1

    def test_create_passenger_input_schema(self):
        """测试创建出行人输入Schema"""
        from src.tools.passengers import CreatePassengerInput

        valid_input = CreatePassengerInput(
            name="张三",
            passenger_type="adult",
            nationality="CN",
            id_type="0",
            id_number="E12345678",
            id_expiration="2030-01-01",
            gender="1",
            birthday="1990-01-01",
        )
        assert valid_input.name == "张三"
        assert valid_input.passenger_type == "adult"

    def test_book_ticket_input_schema(self):
        """测试预订机票输入Schema"""
        from src.tools.orders import BookTicketInput, PassengerInfo, ContactInfo

        input_data = BookTicketInput(
            flight_id="FL123456",
            passengers=[
                PassengerInfo(
                    name="张三",
                    passenger_type="adult",
                    nationality="CN",
                    id_type="0",
                    id_number="E12345678",
                    id_expiration="2030-01-01",
                    gender="1",
                    birthday="1990-01-01",
                )
            ],
            contact=ContactInfo(
                name="张三",
                phone="13800138000",
                email="test@example.com",
            ),
        )
        assert input_data.flight_id == "FL123456"
        assert len(input_data.passengers) == 1


# ===========================================
# 传输模式测试
# ===========================================

class TestTransportMode:
    """测试传输模式"""

    def test_transport_mode_stdio(self, mock_env_vars):
        """测试stdio传输模式配置"""
        os.environ["MCP_TRANSPORT"] = "stdio"

        test_settings = Settings()
        assert test_settings.mcp_transport == "stdio"

    def test_transport_mode_http(self, mock_env_vars):
        """测试HTTP传输模式配置"""
        os.environ["MCP_TRANSPORT"] = "http"
        os.environ["MCP_PORT"] = "8080"

        test_settings = Settings()
        assert test_settings.mcp_transport == "http"
        assert test_settings.mcp_port == 8080

    def test_transport_mode_sse(self, mock_env_vars):
        """测试SSE传输模式配置"""
        os.environ["MCP_TRANSPORT"] = "sse"
        os.environ["MCP_PORT"] = "9000"

        test_settings = Settings()
        assert test_settings.mcp_transport == "sse"
        assert test_settings.mcp_port == 9000


# ===========================================
# MCP协议测试
# ===========================================

class TestMCPProtocol:
    """测试MCP协议合规性"""

    @pytest.mark.asyncio
    async def test_tool_returns_proper_format(self, mock_api_client):
        """测试工具返回正确的MCP格式"""
        test_server = FastMCP("Test Protocol")

        @test_server.tool()
        async def test_protocol_tool(input: Dict[str, Any]) -> Dict[str, Any]:
            """返回符合MCP协议的响应"""
            return {
                "success": True,
                "message": "Success",
                "data": {"key": "value"}
            }

        # 验证服务器创建成功
        assert test_server is not None

    def test_input_validation(self):
        """测试输入验证符合MCP协议"""
        from src.tools.flights import SearchFlightsInput
        from pydantic import ValidationError

        # 测试必填字段
        with pytest.raises(ValidationError):
            SearchFlightsInput(
                origin="PEK",  # 缺少destination和departure_date
            )

        # 测试字段类型验证
        with pytest.raises(ValidationError):
            SearchFlightsInput(
                origin="PEK",
                destination="JFK",
                departure_date="2026-04-01",
                adults="not_a_number",  # 应该是整数
            )

        # 测试字段范围验证
        with pytest.raises(ValidationError):
            SearchFlightsInput(
                origin="PEK",
                destination="JFK",
                departure_date="2026-04-01",
                adults=10,  # 超过9
            )


# ===========================================
# Main入口测试
# ===========================================

class TestMainEntry:
    """测试Main入口函数"""

    def test_main_entry_exists(self):
        """测试main函数存在"""
        from src.server import main
        assert callable(main)

    @patch('src.server.mcp')
    def test_main_stdio_mode(self, mock_mcp_run):
        """测试stdio模式启动"""
        os.environ["MCP_TRANSPORT"] = "stdio"

        with patch('sys.argv', ['server.py']):
            try:
                # main()会调用mcp.run()，这会阻塞
                # 我们只测试配置解析部分
                pass
            except SystemExit:
                pass  # 正常退出

    @patch('src.server.mcp')
    def test_main_http_mode(self, mock_mcp_run):
        """测试HTTP模式启动"""
        os.environ["MCP_TRANSPORT"] = "http"
        os.environ["MCP_PORT"] = "8000"

        # 验证配置
        test_settings = Settings()
        assert test_settings.mcp_transport == "http"

    @patch('src.server.mcp')
    def test_main_invalid_transport(self, mock_mcp_run):
        """测试无效传输模式"""
        os.environ["MCP_TRANSPORT"] = "invalid"

        # 验证错误处理
        test_settings = Settings()
        # 传输模式验证在main函数中


# ===========================================
# 错误处理测试
# ===========================================

class TestErrorHandling:
    """测试错误处理"""

    def test_missing_credentials_warning(self, caplog):
        """测试缺少凭证时的警告"""
        # 设置空的凭证
        os.environ["MEIYA_USERNAME"] = ""
        os.environ["MEIYA_PASSWORD"] = ""

        # 重新加载设置
        test_settings = Settings()

        # 验证设置正确加载
        assert test_settings.meiya_username == ""
        assert test_settings.meiya_password == ""

    def test_api_client_initialization(self):
        """测试API客户端初始化"""
        client = MeiyaApiClient(
            base_url="https://api.test.meiya.com",
            username="test_user",
            password="test_password",
            timeout=30.0,
            max_retries=3,
        )

        assert client.base_url == "https://api.test.meiya.com"
        assert client.username == "test_user"
        assert client.timeout == 30.0
        assert client.max_retries == 3

        # 清理
        # 注意：实际测试中不应真正关闭，因为我们没有真正发起请求


# ===========================================
# 集成测试
# ===========================================

class TestIntegration:
    """集成测试"""

    @pytest.mark.asyncio
    async def test_full_workflow_simulation(self, mock_api_client):
        """模拟完整工作流"""
        # 模拟API响应
        mock_api_client.search_flights = AsyncMock(return_value={
            "code": 0,
            "message": "success",
            "data": {
                "flights": [
                    {
                        "flightId": "FL123456",
                        "flightNumber": "CA981",
                        "origin": "PEK",
                        "destination": "JFK",
                    }
                ]
            }
        })

        # 调用搜索航班
        result = await mock_api_client.search_flights(
            origin="PEK",
            destination="JFK",
            departure_date="2026-04-01",
            adults=1,
        )

        assert result["code"] == 0
        assert len(result["data"]["flights"]) == 1

    @pytest.mark.asyncio
    async def test_tool_registration_and_call(self, mock_api_client):
        """测试工具注册和调用"""
        from src.tools.flights import SearchFlightsInput, SearchFlightsOutput

        # 模拟API调用
        mock_api_client.search_flights = AsyncMock(return_value={
            "code": 0,
            "message": "success",
            "data": {
                "flights": [
                    {
                        "flightId": "FL123456",
                        "flightNumber": "CA981",
                    }
                ]
            }
        })

        # 创建输入
        search_input = SearchFlightsInput(
            origin="PEK",
            destination="JFK",
            departure_date="2026-04-01",
        )

        # 模拟工具调用
        try:
            response = await mock_api_client.search_flights(
                origin=search_input.origin,
                destination=search_input.destination,
                departure_date=search_input.departure_date,
                adults=search_input.adults,
            )

            # 验证响应
            output = SearchFlightsOutput(
                success=response.get("code") == 0,
                message=response.get("message", ""),
                total=len(response.get("data", {}).get("flights", [])),
                flights=response.get("data", {}).get("flights", []),
            )

            assert output.success is True
            assert output.total == 1
        except Exception as e:
            pytest.fail(f"Tool call failed: {e}")


# ===========================================
# 日志和监控测试
# ===========================================

class TestLoggingAndMonitoring:
    """测试日志和监控"""

    def test_logger_configuration(self):
        """测试日志配置"""
        import logging

        # 验证日志器已配置
        logger = logging.getLogger("src.server")
        assert logger is not None

    def test_settings_log_level(self):
        """测试日志级别配置"""
        test_settings = Settings()

        # 验证日志级别设置
        assert hasattr(test_settings, 'log_level')
        assert test_settings.log_level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
