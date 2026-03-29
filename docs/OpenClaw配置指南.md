# 腾云商旅 MCP Server 使用指南

## 一、完整流程概览（8步）

| 步骤 | 操作 | 执行者 | 说明 |
|------|------|--------|------|
| 1 | 运营后台创建公司 | 腾云管理员 | 在腾云运营后台完成 |
| **2** | **分配 AppKey/AppSecret** | **腾云管理员** | **在腾云运营后台完成** |
| 3 | 配置公司密钥 | 小龙虾/OpenClaw | 在环境变量中配置 |
| 4 | 创建用户账号 | MCP工具 | 一次性操作 |
| 5 | 用户登录 | MCP工具 | 获取Token |
| 6 | 查询国际航班 | MCP工具 | 步骤5前置 |
| 7 | 创建出行人 | MCP工具 | 步骤5前置 |
| 8 | 国际机票下单 | MCP工具 | 需要步骤6、7 |

---

## 二、步骤1-2（腾云运营后台）

### 步骤1：创建公司
在腾云运营后台 → 公司管理 → 创建公司

### 步骤2：分配 AppKey/AppSecret
在腾云运营后台 → 公司管理 → 公司列表 → 创建账号密钥

获得：
- **AppKey**: `2110171300000008`
- **AppSecret**: `AWUJy70toNfnKcRpOlowEXMuxBeGArYL`

---

## 三、服务配置

### 3.1 环境变量配置

在 `openclaw-mcp` 目录下创建 `.env` 文件：

```env
# 公司密钥（必填）- 在腾云运营后台创建公司后获取
ONTUOTU_APP_KEY=2110171300000008
ONTUOTU_APP_SECRET=AWUJy70toNfnKcRpOlowEXMuxBeGArYL

# API 地址
ONTUOTU_BASE_URL=https://sla.ontuotu.com

# MCP 传输模式（stdio/http/sse）
MCP_TRANSPORT=stdio

# 请求超时（秒）
REQUEST_TIMEOUT=30
```

### 3.2 OpenClaw 配置

在 OpenClaw 的 MCP 配置中添加：

```json
{
  "mcpServers": {
    "tengyun-flights": {
      "command": "python",
      "args": ["/path/to/openclaw-mcp/src/server.py"],
      "env": {
        "ONTUOTU_APP_KEY": "2110171300000008",
        "ONTUOTU_APP_SECRET": "AWUJy70toNfnKcRpOlowEXMuxBeGArYL"
      }
    }
  }
}
```

---

## 四、MCP 工具列表

| 工具名称 | 功能 | 对应步骤 |
|---------|------|---------|
| `create_user_account` | 创建用户账号 | 步骤4 |
| `login_user` | 用户登录 | 步骤5 |
| `search_international_flights` | 查询国际航班 | 步骤6 |
| `create_passenger` | 创建出行人 | 步骤7 |
| `list_passengers` | 查询出行人列表 | 步骤5后 |
| `book_international_flight` | 国际机票下单 | 步骤8 |
| `full_booking_workflow` | 完整预订流程（步骤5-8） | 步骤4后 |
| `city_to_airports` | 城市→机场转换 | 无 |
| `validate_airport_code` | 验证机场代码 | 无 |
| `search_airports` | 搜索机场 | 无 |
| `query_intl_ticket_rule` | 查询退改签规则 | 步骤5后 |
| `query_intl_order_detail` | 查询订单详情 | 步骤5后 |

---

## 五、标准预订流程（步骤4-8）

### 步骤 4：创建用户账号（一次性）

```json
// 调用 create_user_account
{
  "username": "user001",
  "password": "Pass@123",
  "real_name": "张三",
  "phone": "13800138000"
}
```

**响应示例：**
```json
{
  "success": true,
  "message": "用户账号创建成功"
}
```

---

### 步骤 5：用户登录

```json
// 调用 login_user
{
  "username": "5341746603814055936",
  "password": "T2BoPlKa7dkyAafr"
}
```

**响应示例：**
```json
{
  "success": true,
  "message": "登录成功",
  "token": "eyJhbGciOiJIUzUxMiJ9..."
}
```

---

### 步骤 6：查询国际航班

```json
// 调用 search_international_flights
{
  "from_city": "PEK",
  "to_city": "TYO",
  "from_date": "2026-03-30",
  "adult_count": 1,
  "cabin": "Y"
}
```

**参数说明：**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| from_city | string | 是 | 出发机场代码，如 PEK、PVG、SHA |
| to_city | string | 是 | 目的机场代码，如 TYO、NRT、HND |
| from_date | string | 是 | 出发日期，格式 yyyy-MM-dd |
| trip_type | int | 否 | 1=单程（默认），2=往返 |
| adult_count | int | 否 | 成人数量，默认1 |
| child_count | int | 否 | 儿童数量，默认0 |
| infant_count | int | 否 | 婴儿数量，默认0 |
| cabin | string | 否 | Y=经济舱（默认），C=商务舱，F=头等舱 |

**响应示例：**
```json
{
  "success": true,
  "message": "查询成功，共 91 个航班",
  "flights": [
    {
      "airline_cn": "中国东方航空",
      "airline_en": "China Eastern Airlines",
      "sale_price": "1899",
      "tax": "495",
      "service_fee": "138",
      "total_price": "2532",
      "cabin_name": "经济舱",
      "total_duration": "3h 30m",
      "flight_id": "xxx",
      "segments": [
        {
          "flight_no": "MU5124",
          "dep_airport": "PEK",
          "arr_airport": "HND",
          "dep_time": "2026-03-30 17:30",
          "arr_time": "2026-03-30 21:30"
        }
      ]
    }
  ],
  "total": 91,
  "serial_number": "ea7a45c8bc234826be5fa0792f797bbb"
}
```

---

### 步骤 7：创建出行人

```json
// 调用 create_passenger
{
  "name": "张三",
  "passenger_type": 0,
  "nationality": "CN",
  "id_type": "0",
  "id_number": "E12345678",
  "id_expiration": "2030-12-31",
  "gender": 1,
  "birthday": "1990-01-01",
  "phone": "13800138000"
}
```

**参数说明：**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 是 | 乘客姓名（中文或英文） |
| passenger_type | int | 否 | 0=成人（默认），1=儿童，2=婴儿 |
| nationality | string | 是 | 国籍二字码，如 CN、US、GB |
| id_type | string | 是 | 0=护照，1=其他，3=港澳通行证，4=回乡证，7=台湾通行证，8=台胞证 |
| id_number | string | 是 | 证件号码 |
| id_expiration | string | 是 | 证件有效期，格式 yyyy-MM-dd |
| gender | int | 是 | 1=男，0=女 |
| birthday | string | 是 | 出生日期，格式 yyyy-MM-dd |
| phone | string | 否 | 手机号 |

**响应示例：**
```json
{
  "success": true,
  "message": "出行人创建成功",
  "passenger_id": "37"
}
```

---

### 步骤 8：国际机票下单

```json
// 调用 book_international_flight
{
  "flight_id": "xxx",
  "serial_number": "ea7a45c8bc234826be5fa0792f797bbb",
  "passenger_ids": ["37"],
  "contact_name": "张三",
  "contact_phone": "13800138000",
  "contact_email": "zhangsan@example.com"
}
```

**参数说明：**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| flight_id | string | 是 | 航班ID（来自步骤5的flight_id） |
| serial_number | string | 是 | 序列号（来自步骤5的serial_number） |
| passenger_ids | array | 是 | 出行人ID列表（来自步骤6） |
| contact_name | string | 是 | 联系人姓名 |
| contact_phone | string | 是 | 联系人电话 |
| contact_email | string | 否 | 联系人邮箱 |

**响应示例：**
```json
{
  "success": true,
  "message": "下单成功",
  "order_id": "5343357405528625153",
  "data": {
    "code": "000000",
    "tradeNo": "5343357405528625153"
  }
}
```

---

## 六、便捷工具

### 4.1 完整预订流程（一步完成）

```json
// 调用 full_booking_workflow
{
  "username": "5341746603814055936",
  "password": "T2BoPlKa7dkyAafr",
  "flight_id": "xxx",
  "serial_number": "ea7a45c8bc234826be5fa0792f797bbb",
  "passengers": [
    {
      "name": "张三",
      "passenger_type": 0,
      "nationality": "CN",
      "id_type": "0",
      "id_number": "E12345678",
      "id_expiration": "2030-12-31",
      "gender": 1,
      "birthday": "1990-01-01"
    }
  ],
  "contact_name": "张三",
  "contact_phone": "13800138000"
}
```

### 4.2 机场查询工具

```json
// 城市转机场
{"city": "北京"}
// 返回: {"airports": [{"code": "PEK", "name": "首都国际机场"}, {"code": "PKX", "name": "大兴国际机场"}]}

// 验证机场代码
{"code": "PEK"}
// 返回: {"valid": true, "airport": {...}}

// 搜索机场
{"keyword": "东京", "limit": 5}
// 返回: {"airports": [...]}
```

---

## 七、常用机场代码参考

### 中国出发城市
| 城市 | 机场代码 | 机场名称 |
|------|---------|---------|
| 北京 | PEK | 首都国际机场 |
| 北京 | PKX | 大兴国际机场 |
| 上海 | PVG | 浦东国际机场 |
| 上海 | SHA | 虹桥国际机场 |
| 广州 | CAN | 白云国际机场 |
| 深圳 | SZX |宝安国际机场 |
| 成都 | CTU | 双流国际机场 |
| 杭州 | HGH | 萧山国际机场 |

### 热门目的地
| 城市 | 机场代码 | 机场名称 |
|------|---------|---------|
| 东京 | TYO | 东京城市码 |
| 东京 | NRT | 成田国际机场 |
| 东京 | HND | 羽田国际机场 |
| 首尔 | SEL | 首尔城市码 |
| 首尔 | ICN | 仁川国际机场 |
| 大阪 | OSA | 大阪城市码 |
| 大阪 | KIX | 关西国际机场 |
| 香港 | HKG | 香港国际机场 |
| 新加坡 | SIN | 樟宜机场 |
| 悉尼 | SYD | 金斯福德史密斯机场 |
| 洛杉矶 | LAX | 洛杉矶国际机场 |
| 旧金山 | SFO | 旧金山国际机场 |
| 纽约 | NYC | 纽约城市码 |
| 纽约 | JFK | 肯尼迪国际机场 |
| 伦敦 | LHR | 希思罗机场 |
| 巴黎 | CDG | 戴高乐机场 |

---

## 八、示例对话

### 对话1：查询航班
```
用户：帮我查一下3月30日北京到东京的航班

AI：
{
  "from_city": "PEK",
  "to_city": "TYO",
  "from_date": "2026-03-30",
  "adult_count": 1,
  "cabin": "Y"
}

// 返回：
// ✅ 找到 91 个航班
// 最低价: ¥1899 (中国东方航空)
// MU5124 PEK 17:30 → HND 21:30
```

### 对话2：预订机票
```
用户：我想预订第一个航班，需要创建出行人并下单

AI：好的，我来帮您完成预订流程。

// 1. 创建出行人
{
  "name": "张三",
  "passenger_type": 0,
  "nationality": "CN",
  "id_type": "0",
  "id_number": "E12345678",
  "id_expiration": "2030-12-31",
  "gender": 1,
  "birthday": "1990-01-01"
}

// 2. 下单
{
  "flight_id": "xxx",
  "serial_number": "xxx",
  "passenger_ids": ["37"],
  "contact_name": "张三",
  "contact_phone": "13800138000"
}

// 返回：
// ✅ 预订成功！
// 订单号: 5343357405528625153
```
