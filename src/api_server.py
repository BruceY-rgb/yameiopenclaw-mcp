"""
美亚航旅 API 直接接口服务

使用 FastAPI 将美亚航旅的业务能力暴露为标准的 RESTful HTTP 接口，
替代原先依赖 MCP 协议的服务层暴露方式。

接口参考文档: https://meiya.apifox.cn/

启动方式:
    uvicorn src.api_server:app --host 0.0.0.0 --port 8080 --reload

环境变量（同 .env 文件）:
    MEIYA_API_URL      美亚 API 基础地址
    MEIYA_USERNAME     签约用户名
    MEIYA_PASSWORD     签约密码
    REQUEST_TIMEOUT    请求超时秒数（默认 30）
    MAX_RETRIES        最大重试次数（默认 3）
"""

import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# ============================================================
# 配置
# ============================================================

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", case_sensitive=False)

    meiya_api_url: str = "https://api.meiya.com"
    meiya_username: str = ""
    meiya_password: str = ""
    request_timeout: float = 30.0
    max_retries: int = 3


settings = Settings()


# ============================================================
# 应用生命周期：初始化 API 客户端和工作流编排器
# ============================================================

_api_client = None
_workflow = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _api_client, _workflow

    from src.api.client import MeiyaApiClient
    from src.workflow.orchestrator import WorkflowOrchestrator

    logger.info("初始化美亚航旅 API 服务...")

    if not settings.meiya_username or not settings.meiya_password:
        logger.warning("MEIYA_USERNAME 或 MEIYA_PASSWORD 未配置，接口调用将失败")

    _api_client = MeiyaApiClient(
        base_url=settings.meiya_api_url,
        username=settings.meiya_username,
        password=settings.meiya_password,
        timeout=settings.request_timeout,
        max_retries=settings.max_retries
    )
    _workflow = WorkflowOrchestrator(_api_client)

    logger.info(f"服务初始化完成，API 地址: {settings.meiya_api_url}")
    yield

    logger.info("关闭美亚航旅 API 服务...")
    await _api_client.close()


# ============================================================
# FastAPI 应用实例
# ============================================================

app = FastAPI(
    title="美亚航旅 API 服务",
    description=(
        "将美亚航旅（openclaw）的国际机票查询、计价、预订、支付、取消等能力"
        "以标准 RESTful HTTP 接口对外提供，替代原有 MCP 服务层暴露方式。\n\n"
        "接口参考文档: https://meiya.apifox.cn/"
    ),
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


# ============================================================
# 请求/响应模型
# ============================================================

class OriginDestination(BaseModel):
    """出发-目的地段"""
    dep_airport: str = Field(..., description="出发地机场代码，如 PEK")
    arr_airport: str = Field(..., description="目的地机场代码，如 JFK")
    dep_date: str = Field(..., description="出发日期，格式 YYYY-MM-DD")
    cabin_types: List[str] = Field(
        default=["0"],
        description="舱位等级列表：0=经济舱 1=豪华经济舱 3=商务舱 4=头等舱"
    )


class PassengerCount(BaseModel):
    """乘客数量"""
    passenger_type: int = Field(
        ...,
        description="乘客类型：0=成人 1=儿童 2=婴儿 4=学生"
    )
    count: int = Field(..., ge=1, description="人数")


class SearchFlightsRequest(BaseModel):
    """航班查询请求"""
    dep_airport: str = Field(..., description="出发地机场代码，如 PEK")
    arr_airport: str = Field(..., description="目的地机场代码，如 JFK")
    dep_date: str = Field(..., description="出发日期，格式 YYYY-MM-DD")
    adults: int = Field(default=1, ge=1, le=9, description="成人数量")
    children: int = Field(default=0, ge=0, le=5, description="儿童数量")
    infants: int = Field(default=0, ge=0, le=2, description="婴儿数量")
    cabin_types: List[str] = Field(
        default=["0"],
        description="舱位等级列表：0=经济舱 1=豪华经济舱 3=商务舱 4=头等舱"
    )
    trip_type: str = Field(
        default="1",
        description="行程类别：1=单程 2=往返 3=联程 4=缺口程"
    )
    is_direction: str = Field(
        default="0",
        description="飞行偏好：0=不限 1=直飞 2=最大中转1次 3=最大中转2次"
    )
    is_async: bool = Field(default=False, description="是否异步查询")
    return_date: Optional[str] = Field(None, description="返程日期（往返时使用）")


class PricingRequest(BaseModel):
    """计价请求（实时航班计价模式）"""
    flight_id: str = Field(..., description="航班 ID（Shopping 接口返回的 flightID）")
    serial_number: str = Field(..., description="Shopping 接口返回的 serialNumber")
    airline: str = Field(..., description="出票航司二字码，如 CA、MU")
    adults: int = Field(default=1, ge=1, description="成人数量")
    children: int = Field(default=0, ge=0, description="儿童数量")
    infants: int = Field(default=0, ge=0, description="婴儿数量")
    is_async: bool = Field(default=False, description="是否异步计价")


class PassengerInfo(BaseModel):
    """乘客信息（生单时使用）"""
    name: str = Field(..., description="乘客姓名")
    passenger_type: str = Field(
        default="0",
        description="乘客类型：0=成人 1=儿童 2=婴儿 3=老人 4=学生"
    )
    nationality: str = Field(..., description="国籍二字代码，如 CN")
    id_type: str = Field(
        ...,
        description="证件类型：0=护照 1=其他 3=港澳通行证 4=回乡证 7=台湾通行证 8=台胞证 9=军人证"
    )
    id_number: str = Field(..., description="证件号码")
    id_nationality: Optional[str] = Field(None, description="证件签发国二字码，默认与国籍相同")
    id_expiration: str = Field(..., description="证件有效期，格式 YYYY-MM-DD")
    gender: str = Field(..., description="性别：1=男 0=女")
    birthday: str = Field(..., description="出生日期，格式 YYYY-MM-DD")
    phone_number: Optional[str] = Field(None, description="手机号")
    email: Optional[str] = Field(None, description="邮箱")


class ContactInfo(BaseModel):
    """联系人信息"""
    linker: str = Field(..., description="联系人姓名")
    phone: str = Field(..., description="联系人手机号")
    email: Optional[str] = Field(None, description="联系人邮箱")
    is_email: str = Field(default="0", description="出票邮件通知：0=不通知 1=通知")
    is_sms: str = Field(default="0", description="出票短信通知：0=不通知 1=通知")


class CreateOrderRequest(BaseModel):
    """生单请求（实时航班下单模式）"""
    policy_serial_number: str = Field(..., description="计价接口返回的 policySerialNumber")
    create_order_type: int = Field(
        default=1,
        description="下单方式：1=实时航班下单 2=PNR下单 3=航段导入下单"
    )
    passengers: List[PassengerInfo] = Field(..., description="乘客列表")
    contact: ContactInfo = Field(..., description="联系人信息")
    pnr: Optional[str] = Field(None, description="PNR（createOrderType 为 2/3 时必填）")
    is_convert: int = Field(default=0, description="是否转编码：1=转 0=不转")
    qd_order_id: Optional[str] = Field(None, description="第三方订单号（可选）")


class BookingWorkflowRequest(BaseModel):
    """完整预订工作流请求（一步完成：查询→计价→生单→验价验舱）"""
    dep_airport: str = Field(..., description="出发地机场代码，如 PEK")
    arr_airport: str = Field(..., description="目的地机场代码，如 JFK")
    dep_date: str = Field(..., description="出发日期，格式 YYYY-MM-DD")
    airline: str = Field(..., description="出票航司二字码，如 CA、MU")
    passengers: List[PassengerInfo] = Field(..., description="乘客列表")
    contact: ContactInfo = Field(..., description="联系人信息")
    adults: int = Field(default=1, ge=1, description="成人数量")
    children: int = Field(default=0, ge=0, description="儿童数量")
    infants: int = Field(default=0, ge=0, description="婴儿数量")
    cabin_types: List[str] = Field(default=["0"], description="舱位等级列表")
    trip_type: str = Field(default="1", description="行程类别")
    flight_id: Optional[str] = Field(None, description="航班 ID（已知时跳过查询步骤）")
    serial_number: Optional[str] = Field(None, description="serialNumber（已知时跳过查询步骤）")


class PayOrderRequest(BaseModel):
    """支付订单请求"""
    payment_method: str = Field(default="online", description="支付方式：online/offline")


class CancelOrderRequest(BaseModel):
    """取消订单请求"""
    reason: Optional[str] = Field(None, description="取消原因")


class FlightChangeQueryRequest(BaseModel):
    """航变查询请求"""
    begin_date: str = Field(..., description="查询开始时间，格式 yyyy-MM-dd")
    end_date: str = Field(..., description="查询结束时间，格式 yyyy-MM-dd")
    order_id: Optional[str] = Field(None, description="TO 或 TC 订单号（可选）")
    status: int = Field(default=-1, description="航变状态：-1=所有 0=未查阅 1=已查阅")
    page_index: int = Field(default=1, ge=1, description="页码，从 1 开始")
    page_size: int = Field(default=20, ge=1, le=100, description="每页数量，最大 100")


# ============================================================
# 辅助函数
# ============================================================

def get_client():
    if _api_client is None:
        raise HTTPException(status_code=503, detail="API 客户端未初始化，请检查服务配置")
    return _api_client


def get_workflow():
    if _workflow is None:
        raise HTTPException(status_code=503, detail="工作流编排器未初始化，请检查服务配置")
    return _workflow


def _build_passenger_list(passengers: List[PassengerInfo]) -> List[Dict[str, Any]]:
    """将 PassengerInfo 列表转换为美亚 API 所需的 passengerList 格式"""
    result = []
    for pax in passengers:
        pax_data: Dict[str, Any] = {
            "name": pax.name,
            "passengerType": pax.passenger_type,
            "nationality": pax.nationality,
            "idType": pax.id_type,
            "idNumber": pax.id_number,
            "idExpiration": pax.id_expiration,
            "gender": pax.gender,
            "birthday": pax.birthday
        }
        if pax.id_nationality:
            pax_data["idNationality"] = pax.id_nationality
        if pax.phone_number:
            pax_data["phoneNumber"] = pax.phone_number
        if pax.email:
            pax_data["email"] = pax.email
        result.append(pax_data)
    return result


def _build_contact(contact: ContactInfo) -> Dict[str, Any]:
    """将 ContactInfo 转换为美亚 API 所需的 contact 格式"""
    return {
        "linker": contact.linker,
        "phone": contact.phone,
        "email": contact.email,
        "isEmail": contact.is_email,
        "isSMS": contact.is_sms
    }


# ============================================================
# 健康检查
# ============================================================

@app.get("/health", tags=["系统"], summary="健康检查")
async def health_check():
    """返回服务健康状态"""
    return {
        "status": "ok",
        "service": "美亚航旅 API 服务",
        "version": "2.0.0",
        "api_url": settings.meiya_api_url,
        "configured": bool(settings.meiya_username and settings.meiya_password)
    }


# ============================================================
# 航班查询接口
# ============================================================

@app.post(
    "/api/flights/search",
    tags=["航班"],
    summary="国际机票航班查询（Shopping）",
    description=(
        "查询国际机票航班，支持单程、往返、联程。\n\n"
        "对应美亚 API: POST /SupplierIntlTicket/v2/Shopping\n\n"
        "同步模式直接返回航班列表；异步模式（is_async=true）返回 serialNumber，"
        "需再调用 /api/flights/async-result 获取结果。"
    )
)
async def search_flights(request: SearchFlightsRequest):
    client = get_client()
    try:
        result = await client.search_flights(
            dep_airport=request.dep_airport,
            arr_airport=request.arr_airport,
            dep_date=request.dep_date,
            adults=request.adults,
            children=request.children,
            infants=request.infants,
            cabin_types=request.cabin_types,
            trip_type=request.trip_type,
            is_direction=request.is_direction,
            is_async=request.is_async,
            return_date=request.return_date
        )
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"航班查询失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/api/flights/async-result",
    tags=["航班"],
    summary="获取异步查询结果（ShoppingDataQuery）",
    description="获取 Shopping 异步模式返回的航班查询结果。\n\n对应美亚 API: POST /SupplierIntlTicket/v2/ShoppingDataQuery"
)
async def get_shopping_data(serial_number: str = Query(..., description="Shopping 接口返回的 serialNumber")):
    client = get_client()
    try:
        result = await client.get_shopping_data(serial_number)
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"获取异步查询结果失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/api/flights/more-price",
    tags=["航班"],
    summary="获取更多价格（全舱位）（ShoppingMorePrice）",
    description="获取指定航班所有舱位的价格信息。\n\n对应美亚 API: POST /SupplierIntlTicket/v2/ShoppingMorePrice"
)
async def get_more_price(
    flight_id: str = Query(..., description="航班 ID"),
    serial_number: str = Query(..., description="serialNumber")
):
    client = get_client()
    try:
        result = await client.get_more_price(flight_id, serial_number)
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"获取更多价格失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/api/flights/ticket-rule",
    tags=["航班"],
    summary="查询退改签规则（TicketRuleQuery）",
    description="查询指定航班的退票、改签、签转规则及费用。\n\n对应美亚 API: POST /SupplierIntlTicket/v2/TicketRuleQuery"
)
async def query_ticket_rule(
    flight_id: str = Query(..., description="航班 ID"),
    serial_number: str = Query(..., description="serialNumber")
):
    client = get_client()
    try:
        result = await client.query_ticket_rule(flight_id, serial_number)
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"查询退改签规则失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/api/flights/stopover",
    tags=["航班"],
    summary="查询经停信息（StopoverQuery）",
    description="查询航班是否有经停及经停详情。\n\n对应美亚 API: POST /SupplierIntlTicket/v2/StopoverQuery"
)
async def query_stopover(
    flight_id: str = Query(..., description="航班 ID"),
    serial_number: str = Query(..., description="serialNumber")
):
    client = get_client()
    try:
        result = await client.query_stopover(flight_id, serial_number)
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"查询经停信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/api/flights/details",
    tags=["航班"],
    summary="航班明细查询（ShoppingFlight）",
    description="获取指定航班的详细信息。\n\n对应美亚 API: POST /SupplierIntlTicket/v2/ShoppingFlight"
)
async def get_flight_details(
    flight_id: str = Query(..., description="航班 ID"),
    serial_number: str = Query(..., description="serialNumber")
):
    client = get_client()
    try:
        result = await client.get_flight_details(flight_id, serial_number)
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"获取航班明细失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# 计价接口
# ============================================================

@app.post(
    "/api/pricing",
    tags=["计价"],
    summary="国际机票计价（Pricing）- 实时航班计价模式",
    description=(
        "对指定航班进行计价，获取 policySerialNumber 用于后续下单。\n\n"
        "对应美亚 API: POST /SupplierIntlTicket/v2/Pricing\n\n"
        "本接口使用**实时航班计价模式**，需同时传入 flight_id 和 serial_number。"
    )
)
async def pricing(request: PricingRequest):
    client = get_client()
    try:
        passengers = []
        if request.adults > 0:
            passengers.append({"passengerType": 0, "passengerCount": request.adults})
        if request.children > 0:
            passengers.append({"passengerType": 1, "passengerCount": request.children})
        if request.infants > 0:
            passengers.append({"passengerType": 2, "passengerCount": request.infants})

        result = await client.pricing(
            flight_id=request.flight_id,
            serial_number=request.serial_number,
            airline=request.airline,
            passengers=passengers,
            is_async=request.is_async
        )
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"计价失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/api/pricing/async-result",
    tags=["计价"],
    summary="获取异步计价结果（PricingDataQuery）",
    description="获取 Pricing 异步模式返回的计价结果。\n\n对应美亚 API: POST /SupplierIntlTicket/v2/PricingDataQuery"
)
async def get_pricing_data(request_key: str = Query(..., description="Pricing 接口异步模式返回的 requestKey")):
    client = get_client()
    try:
        result = await client.get_pricing_data(request_key)
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"获取异步计价结果失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# 订单接口
# ============================================================

@app.post(
    "/api/orders",
    tags=["订单"],
    summary="国际机票订单采购生单（TOOrderSave）",
    description=(
        "创建机票订单（生单）。支持三种下单模式：\n\n"
        "- `create_order_type=1`：实时航班下单（需 policySerialNumber）\n"
        "- `create_order_type=2`：PNR 下单\n"
        "- `create_order_type=3`：航段导入下单\n\n"
        "对应美亚 API: POST /SupplierIntlToOrder/v2/TOOrderSave"
    )
)
async def create_order(request: CreateOrderRequest):
    client = get_client()
    try:
        order_data = {
            "policySerialNumber": request.policy_serial_number,
            "createOrderType": request.create_order_type,
            "isConvert": request.is_convert,
            "passengerList": _build_passenger_list(request.passengers),
            "contact": _build_contact(request.contact)
        }
        if request.pnr:
            order_data["pnr"] = request.pnr
        if request.qd_order_id:
            order_data["qdOrderID"] = request.qd_order_id

        result = await client.create_order(order_data)
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"生单失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/api/orders/{order_id}",
    tags=["订单"],
    summary="查询订单详情（TOOrderDetailQuery）",
    description="获取订单的详细信息，包括订单状态、航班信息、乘客信息、价格明细等。\n\n对应美亚 API: POST /SupplierIntlToOrder/v2/TOOrderDetailQuery"
)
async def query_order(order_id: str):
    client = get_client()
    try:
        result = await client.query_order(order_id)
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"查询订单失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/api/orders/{order_id}/verify",
    tags=["订单"],
    summary="订单验价验舱（OrderPayVer）",
    description="在支付前对订单进行验价验舱，确认价格和座位仍然有效。\n\n对应美亚 API: POST /SupplierIntlToOrder/v2/OrderPayVer"
)
async def verify_order(order_id: str):
    client = get_client()
    try:
        result = await client.verify_order(order_id)
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"验价验舱失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/api/orders/{order_id}/pay",
    tags=["订单"],
    summary="确认支付订单（OrderPayConfirm + 验价验舱工作流）",
    description=(
        "执行完整支付工作流：先验价验舱，再确认支付。\n\n"
        "对应美亚 API:\n"
        "- POST /SupplierIntlToOrder/v2/OrderPayVer\n"
        "- POST /SupplierIntlToOrder/v2/OrderPayConfirm"
    )
)
async def pay_order(order_id: str, request: PayOrderRequest):
    workflow = get_workflow()
    try:
        result = await workflow.execute_payment_workflow(order_id, request.payment_method)
        return result
    except Exception as e:
        logger.error(f"支付失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/api/orders/{order_id}/cancel",
    tags=["订单"],
    summary="取消订单（TOOrderCancel）",
    description="取消机票订单。注意：已出票的订单可能需要走退票流程。\n\n对应美亚 API: POST /SupplierIntlToOrder/v2/TOOrderCancel"
)
async def cancel_order(order_id: str, request: CancelOrderRequest):
    workflow = get_workflow()
    try:
        result = await workflow.execute_cancel_workflow(order_id, request.reason)
        return result
    except Exception as e:
        logger.error(f"取消订单失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# 完整预订工作流（一步完成）
# ============================================================

@app.post(
    "/api/orders/book",
    tags=["订单"],
    summary="完整预订工作流（查询→计价→生单→验价验舱）",
    description=(
        "一步完成完整的机票预订流程：\n\n"
        "1. 查询航班（Shopping）\n"
        "2. 计价（Pricing）\n"
        "3. 生单（TOOrderSave）\n"
        "4. 验价验舱（OrderPayVer）\n\n"
        "若已知 flight_id 和 serial_number，可直接跳过查询步骤。\n"
        "成功后返回 order_id，需再调用 /api/orders/{order_id}/pay 完成支付。"
    )
)
async def book_ticket(request: BookingWorkflowRequest):
    workflow = get_workflow()
    try:
        context = {
            "dep_airport": request.dep_airport,
            "arr_airport": request.arr_airport,
            "dep_date": request.dep_date,
            "airline": request.airline,
            "adults": request.adults,
            "children": request.children,
            "infants": request.infants,
            "cabin_types": request.cabin_types,
            "trip_type": request.trip_type,
            "passengers": _build_passenger_list(request.passengers),
            "contact": _build_contact(request.contact)
        }
        if request.flight_id:
            context["flight_id"] = request.flight_id
        if request.serial_number:
            context["serial_number"] = request.serial_number

        result = await workflow.execute_booking_workflow(context)
        return result
    except Exception as e:
        logger.error(f"预订工作流失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# 航变查询
# ============================================================

@app.post(
    "/api/flight-changes",
    tags=["航变"],
    summary="查询航变信息（VoyageChangeLibraryQuery）",
    description="查询客户部门的航班变更消息，包括延误、取消、时刻变更等。\n\n对应美亚 API: POST /SupplierTicketCommon/v2/VoyageChangeLibraryQuery"
)
async def get_flight_changes(request: FlightChangeQueryRequest):
    client = get_client()
    try:
        result = await client.get_flight_change(
            begin_date=request.begin_date,
            end_date=request.end_date,
            order_id=request.order_id,
            status=request.status,
            page_index=request.page_index,
            page_size=request.page_size
        )
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"查询航变失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
