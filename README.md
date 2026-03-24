# 美亚航旅API MCP Server

基于美亚航旅API (https://meiya.apifox.cn/) 开发的MCP Server，提供国际机票查询、预订、支付等功能。

## 功能特性

- ✈️ 航班查询 - 支持单程/往返、国际航班
- 👤 出行人管理 - 创建、更新、查询乘客信息
- 🎫 机票预订 - 完整预订流程（计价→生单→验价）
- 💳 订单支付 - 支持在线/线下支付
- ❌ 订单取消 - 未支付订单取消

## 环境要求

- Python 3.10+
- uv (推荐) 或 pip

## 快速开始

### 1. 安装依赖

```bash
# 使用uv（推荐）
uv venv && uv pip install -r requirements.txt

# 或使用pip
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
# 复制示例配置
cp .env.example .env

# 编辑 .env，填入你的API凭证
# MEIYA_USERNAME=你的用户名
# MEIYA_PASSWORD=你的密码
```

### 3. 运行服务

**stdio模式**（适合Claude Desktop）：
```bash
python -m src.server
```

**HTTP模式**（适合远程调用）：
```bash
MCP_TRANSPORT=http python -m src.server
# 访问 http://localhost:8000
```

## MCP工具

| 工具 | 功能 |
|------|------|
| `search_international_flights` | 查询国际航班 |
| `get_flight_details` | 获取航班详情 |
| `pricing_flight` | 航班计价 |
| `create_passenger` | 创建出行人 |
| `update_passenger` | 更新出行人 |
| `get_passenger` | 获取出行人信息 |
| `book_ticket` | 预订机票（完整流程） |
| `query_order` | 查询订单 |
| `pay_order` | 支付订单 |
| `cancel_order` | 取消订单 |

## 示例

### 查询航班

```python
# 输入参数
{
    "origin": "PEK",           # 出发地机场代码
    "destination": "JFK",       # 目的地机场代码
    "departure_date": "2026-04-01",  # 出发日期
    "adults": 1,                # 成人数量
    "cabin_class": "economy"    # 舱位等级
}
```

### 预订机票

```python
{
    "flight_id": "FL123456",
    "passengers": [{
        "name": "张三",
        "nationality": "CN",
        "id_type": "0",
        "id_number": "E12345678",
        "id_expiration": "2030-01-01",
        "gender": "1",
        "birthday": "1990-01-01"
    }],
    "contact": {
        "name": "张三",
        "phone": "13800138000"
    }
}
```

## 测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行特定测试
pytest tests/test_client.py -v
```

## Docker部署

```bash
cd docker
docker-compose up -d
```

## 项目结构

```
meiya-mcp-server/
├── src/
│   ├── api/client.py       # API客户端
│   ├── auth/manager.py     # 认证管理
│   ├── workflow/orchestrator.py  # 工作流
│   ├── tools/              # MCP工具
│   └── server.py           # 主入口
├── tests/                  # 测试
├── docker/                 # Docker配置
└── requirements.txt        # 依赖
```

## 注意事项

1. API凭证需联系美亚航旅获取
2. Token认证：MD5(username + password + timestamp + body) + Base64
3. 客户端和服务器时间差不能超过5分钟

## 许可证

MIT