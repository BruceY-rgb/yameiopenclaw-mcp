# 美亚航旅 MCP 服务层改造方案

**作者**: Manus AI
**日期**: 2026-03-24

## 1. 背景与目标

当前 `yameiopenclaw-mcp` 仓库实现了一个基于 FastMCP 的美亚航旅 API 服务端。其主要问题在于：**MCP 方案的服务层暴露在外面了**。这意味着原有的设计是让 LLM 客户端（如 Claude Desktop）通过 MCP 协议直接调用各种高层业务工具（如 `book_ticket`），而在某些场景下（如已有后端服务或工作流引擎），这种通过 MCP 暴露的方式并不适用，客户希望**通过直接调用接口的方式**来解决问题。

**目标**：将现有的基于 MCP 工具暴露的业务能力，重构或补充为可以直接通过 HTTP API 调用的方式，并修正底层调用美亚航旅接口的路径差异。

## 2. 现状分析

目前代码分为四层：
1. **API 客户端层 (`src/api/client.py`)**：负责底层的 Token 签名和 HTTP 请求。
2. **工作流编排层 (`src/workflow/orchestrator.py`)**：负责串联多步 API 调用（如：查航班 -> 计价 -> 创建乘机人 -> 生单 -> 验价验舱）。
3. **MCP 工具层 (`src/tools/*.py`)**：定义了输入输出模型，并将工作流或 API 暴露为 MCP Tool。
4. **MCP 服务层 (`src/server.py`)**：使用 FastMCP 启动服务，支持 stdio、sse 等传输方式。

**问题发现**：
在对比了官方接口文档（https://meiya.apifox.cn/）后，发现当前 `client.py` 中的请求路径与官方文档不符。例如：
- 官方文档 Shopping 接口：`/supplier/supplierapi/thgeneralinterface/SupplierIntlTicket/v2/Shopping`
- 当前代码 Shopping 接口：`/supplier/supplierapi/thgeneralinterface/SupplierIntlToSearch/v2/Shopping`

## 3. 改造方案

为了解决“服务层暴露”的问题，我们需要将 FastMCP 替换或补充为标准的 HTTP API 框架（如 FastAPI），使得其他系统可以直接通过 RESTful API 调用这些功能，而不是必须通过 MCP 协议。

### 3.1. 底层 API 路径修正
首先，需要修改 `src/api/client.py` 中的所有请求路径，使其与最新的美亚航旅官方 API 文档保持一致。主要将路径中的模块名（如 `SupplierIntlToSearch`、`SupplierIntlToPricing`、`SupplierIntlToOrder`）统一替换为文档中指定的模块名（大部分为 `SupplierIntlTicket`，部分为 `SupplierTicketCommon`）。

### 3.2. 引入 FastAPI 提供直接接口调用
不改变现有的核心业务逻辑（`MeiyaApiClient` 和 `WorkflowOrchestrator`），在 `src` 目录下新建一个 `api_server.py`，使用 `FastAPI` 将这些能力包装成标准的 RESTful API。

提供的核心接口包括：
- **航班查询**: `POST /api/flights/search`
- **航班计价**: `POST /api/flights/pricing`
- **机票预订（工作流）**: `POST /api/orders/book`
- **订单查询**: `GET /api/orders/{order_id}`
- **订单支付（工作流）**: `POST /api/orders/{order_id}/pay`
- **订单取消**: `POST /api/orders/{order_id}/cancel`

### 3.3. 移除或保留 MCP 层的决策
考虑到客户的诉求是“想通过直接去调用接口的方式解决问题”，我们可以：
1. 保留原有的 `server.py` (MCP 方式) 作为可选启动项。
2. 提供新的 `api_server.py` (FastAPI 方式) 作为主要的直接接口调用方式。
3. 修改 `docker-compose.yml` 和启动脚本，支持启动 FastAPI 服务。

## 4. 实施步骤

1. **步骤一**：修改 `src/api/client.py`，修正所有美亚 API 的请求路径。
2. **步骤二**：创建 `src/api_server.py`，使用 FastAPI 包装 `MeiyaApiClient` 和 `WorkflowOrchestrator`。
3. **步骤三**：编写测试脚本，验证直接 API 调用的连通性。
4. **步骤四**：更新文档，说明如何启动和调用直接接口。

## 5. 预期收益
通过此次改造，客户的内部系统可以直接通过 HTTP POST/GET 请求调用美亚航旅的各项能力及预订工作流，彻底解决了原先必须依赖 MCP 协议导致的服务层暴露和集成困难问题。
