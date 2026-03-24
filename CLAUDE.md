# 美亚航旅API MCP Server 项目

## 项目概述
基于美亚航旅API (https://meiya.apifox.cn/) 开发的生产级MCP Server，提供国际机票查询、预订、支付等完整业务流程。

## 技术栈
- **框架**: FastMCP (Python)
- **认证**: Token-based (MD5+Base64加密)
- **架构**: 四层架构
- **部署**: Docker / Claude Desktop

## 项目文档
- 调研报告: `docs/美亚航旅API_MCP_Server调研报告.md`
- 要求每一次执行任务都要阅读一下该报告

---

## 项目进度

### 阶段一：项目基础搭建 ✅
- [x] 创建项目目录结构
- [x] 配置requirements.txt和pyproject.toml
- [x] 创建.env.example环境变量示例
- [x] 配置Dockerfile和docker-compose.yml

### 阶段二：核心模块开发 ✅
- [x] 实现API客户端层 (src/api/client.py)
- [x] 实现认证管理层 (src/auth/manager.py)
- [x] 实现业务逻辑层 (src/workflow/orchestrator.py)

### 阶段三：MCP工具开发 ✅
- [x] 开发航班工具 (src/tools/flights.py)
- [x] 开发出行人工具 (src/tools/passengers.py)
- [x] 开发订单工具 (src/tools/orders.py)
- [x] 集成MCP Server主入口 (src/server.py)

### 阶段四：测试与部署 ✅
- [x] 编写单元测试 (67个)
- [x] 编写MCP框架测试 (30个) - **全部通过**
- [ ] 配置Claude Desktop集成
- [ ] 编写README文档

---

## 项目结构（已创建）

```
openclaw-mcp/
├── CLAUDE.md                 # 项目说明文档
├── requirements.txt          # Python依赖
├── pyproject.toml           # 项目配置
├── .env.example             # 环境变量示例
├── src/
│   ├── __init__.py
│   ├── server.py            # MCP Server主入口
│   ├── api/
│   │   ├── __init__.py
│   │   └── client.py        # API客户端层
│   ├── auth/
│   │   ├── __init__.py
│   │   └── manager.py       # 认证管理层
│   ├── workflow/
│   │   ├── __init__.py
│   │   └── orchestrator.py  # 业务逻辑层
│   └── tools/
│       ├── __init__.py
│       ├── flights.py       # 航班工具
│       ├── passengers.py    # 出行人工具
│       └── orders.py        # 订单工具
├── tests/
│   ├── __init__.py
│   ├── conftest.py           # Pytest配置和fixtures
│   ├── test_client.py        # API客户端测试 (23个)
│   ├── test_auth.py          # 认证管理测试 (18个)
│   ├── test_tools.py         # 工具测试 (26个)
│   └── test_mcp_server.py     # MCP框架测试 (30个)
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
└── docs/
    └── 美亚航旅API_MCP_Server调研报告.md
```

---

## 开发规范

### 代码规范
- 使用Python 3.10+
- 遵循PEP 8规范（line-length: 100）
- 使用类型注解（Type Hints）
- 使用Pydantic进行数据验证
- 异步编程（async/await）

### 命名规范
- 类名: PascalCase (如 `MeiyaApiClient`)
- 函数名: snake_case (如 `search_international_flights`)
- 常量: UPPER_SNAKE_CASE
- 文件名: snake_case

### 目录结构
```
meiya-mcp-server/
├── src/                    # 源代码
│   ├── api/               # API客户端层
│   ├── auth/              # 认证管理层
│   ├── workflow/          # 业务逻辑层
│   └── tools/             # MCP工具层
├── tests/                 # 测试代码
├── config/                # 配置文件
├── docker/                # Docker配置
└── docs/                  # 文档
```

### Git提交规范
- 使用中文提交信息
- 格式: `类型: 描述`
- 类型: feat(新功能), fix(修复), docs(文档), test(测试), refactor(重构)

---

## 核心功能

### API接口列表
| 接口 | 功能 |
|------|------|
| Shopping | 国际机票航班查询 |
| Pricing | 航班计价 |
| TOOrderSave | 生单接口 |
| OrderPayVer | 验价验舱 |
| OrderPayConfirm | 确认支付 |
| TOOrderDetailQuery | 订单详情查询 |
| TOOrderCancel | 订单取消 |

### MCP工具列表
- `search_international_flights` - 查询国际航班
- `get_flight_details` - 获取航班详情
- `pricing_flight` - 航班计价
- `create_passenger` - 创建出行人
- `book_ticket` - 预订机票
- `query_order` - 查询订单
- `pay_order` - 支付订单
- `cancel_order` - 取消订单

---

## 环境变量

| 变量名 | 描述 | 必填 |
|--------|------|------|
| MEIYA_API_URL | API基础URL | 是 |
| MEIYA_USERNAME | API用户名 | 是 |
| MEIYA_PASSWORD | API密码 | 是 |
| MCP_TRANSPORT | 传输模式 (stdio/http/sse) | 否 |
| MCP_PORT | HTTP端口 | 否 |
| LOG_LEVEL | 日志级别 | 否 |

---

## 注意事项

1. **认证机制**: Token生成算法为 `MD5(username + pwd + timestamp + body) + Base64`
2. **时间戳同步**: 客户端和服务器时间差不能超过5分钟
3. **密钥安全**: 敏感信息存储在环境变量中，不要提交到版本控制
4. **错误处理**: 所有API调用需要捕获异常并返回友好的错误信息
