"""
工作流编排器

负责管理多步骤业务流程，包括航班查询、计价、预订、支付等完整工作流。
"""

import logging
from typing import Dict, Any, List, Optional

from src.api.client import MeiyaApiClient
from src.auth.manager import AuthManager

logger = logging.getLogger(__name__)


class WorkflowError(Exception):
    """工作流执行错误"""

    def __init__(self, message: str, step: str = "", details: Optional[Dict] = None):
        super().__init__(message)
        self.message = message
        self.step = step
        self.details = details or {}

    def __str__(self):
        if self.step:
            return f"[步骤: {self.step}] {self.message}"
        return self.message


class WorkflowOrchestrator:
    """工作流编排器

    负责编排和管理多步骤的业务流程，包括：
    - 预订工作流（查询→计价→生单→验价验舱）
    - 支付工作流（验价验舱→确认支付）
    - 取消工作流（取消订单）

    注意：美亚航旅 API 没有独立的"出行人"管理接口，乘客信息直接在生单
    (TOOrderSave) 时通过 passengerList 字段传入，因此本工作流不再包含
    "创建出行人"步骤。
    """

    def __init__(
        self,
        api_client: MeiyaApiClient,
        auth_manager: Optional[AuthManager] = None
    ):
        """初始化工作流编排器

        Args:
            api_client: API客户端实例
            auth_manager: 认证管理器实例（可选，当前美亚 API 使用 Header 签名认证，
                          不依赖 auth_manager，保留参数仅为兼容性）
        """
        self.api_client = api_client
        self.auth_manager = auth_manager

    async def execute_booking_workflow(
        self,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """执行预订工作流

        完整流程：
        1. 查询航班（若未提供 flight_id 和 serial_number）
        2. 计价（Pricing）
        3. 生单（TOOrderSave）
        4. 验价验舱（OrderPayVer）

        Args:
            context: 工作流上下文，必须包含：
                - dep_airport: 出发地机场代码（如 PEK）
                - arr_airport: 目的地机场代码（如 JFK）
                - dep_date: 出发日期（YYYY-MM-DD）
                - airline: 出票航司二字码（如 CA、MU）
                - passengers: 乘客列表（符合 TOOrderSave passengerList 格式）
                - contact: 联系人信息（符合 TOOrderSave contact 格式）
              可选包含：
                - flight_id: 航班 ID（已知时跳过查询步骤）
                - serial_number: Shopping 接口返回的 serialNumber
                - adults: 成人数量（默认 1）
                - children: 儿童数量（默认 0）
                - infants: 婴儿数量（默认 0）
                - cabin_types: 舱位列表（默认 ["0"] 经济舱）
                - create_order_type: 下单方式（默认 1=实时航班）

        Returns:
            工作流执行结果，包含 order_id、status 等
        """
        workflow_context = {
            **context,
            "steps_completed": [],
            "errors": []
        }

        try:
            # 步骤1: 如果没有提供 flight_id，先查询航班
            if not context.get("flight_id") or not context.get("serial_number"):
                flights_result = await self._search_flights(workflow_context)
                if not flights_result:
                    raise WorkflowError("未找到可用航班", step="search_flights")
                workflow_context["steps_completed"].append("search_flights")

            # 步骤2: 计价
            pricing_result = await self._pricing(workflow_context)
            workflow_context["policy_serial_number"] = pricing_result.get("policySerialNumber") or \
                (pricing_result.get("detail") or [{}])[0].get("serialNumber")
            workflow_context["steps_completed"].append("pricing")

            # 步骤3: 生单
            order_result = await self._create_order(workflow_context)
            workflow_context["order_id"] = (
                order_result.get("orderId") or
                (order_result.get("detail") or {}).get("orderId")
            )
            workflow_context["order"] = order_result
            workflow_context["steps_completed"].append("create_order")

            # 步骤4: 验价验舱
            verify_result = await self._verify_order(workflow_context)
            workflow_context["verify_result"] = verify_result
            workflow_context["steps_completed"].append("verify_order")

            logger.info(f"预订工作流完成: order_id={workflow_context.get('order_id')}")

            return {
                "success": True,
                "order_id": workflow_context.get("order_id"),
                "status": "pending_payment",
                "message": "预订成功，请完成支付",
                "steps_completed": workflow_context["steps_completed"]
            }

        except WorkflowError:
            raise
        except Exception as e:
            logger.error(f"预订工作流执行失败: {e}")
            await self._handle_error(e, workflow_context)
            raise WorkflowError(
                f"预订失败: {str(e)}",
                step=workflow_context.get("current_step", "unknown"),
                details={"context": workflow_context}
            )

    async def _search_flights(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """查询航班（内部步骤）

        调用 Shopping 接口，将第一个可用航班的 flightID 和 serialNumber
        写回 context，供后续步骤使用。
        """
        context["current_step"] = "search_flights"

        dep_airport = context.get("dep_airport", "")
        arr_airport = context.get("arr_airport", "")
        dep_date = context.get("dep_date", "")

        logger.info(f"查询航班: {dep_airport} -> {arr_airport}, 日期: {dep_date}")

        response = await self.api_client.search_flights(
            dep_airport=dep_airport,
            arr_airport=arr_airport,
            dep_date=dep_date,
            adults=context.get("adults", 1),
            children=context.get("children", 0),
            infants=context.get("infants", 0),
            cabin_types=context.get("cabin_types", ["0"]),
            trip_type=context.get("trip_type", "1"),
            return_date=context.get("return_date")
        )

        # 解析 Shopping 接口返回结构
        detail = response.get("detail", {})
        serial_number = detail.get("serialNumber")
        flight_list = detail.get("flightDetailList", [])

        if serial_number:
            context["serial_number"] = serial_number

        if flight_list:
            first_flight = flight_list[0]
            context["flight_id"] = first_flight.get("flightID")
            logger.info(f"选取第一个航班: flightID={context['flight_id']}, serialNumber={serial_number}")

        logger.info(f"查询到 {len(flight_list)} 个航班")
        return flight_list

    async def _pricing(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """航班计价（内部步骤）

        使用实时航班计价模式（需要 serialNumber + flightID）。
        """
        context["current_step"] = "pricing"

        flight_id = context.get("flight_id", "")
        serial_number = context.get("serial_number", "")
        airline = context.get("airline", "")

        logger.info(f"计价: flightID={flight_id}, serialNumber={serial_number}")

        # 构建乘客类型列表
        passengers = []
        adults = context.get("adults", 1)
        children = context.get("children", 0)
        infants = context.get("infants", 0)
        if adults > 0:
            passengers.append({"passengerType": 0, "passengerCount": adults})
        if children > 0:
            passengers.append({"passengerType": 1, "passengerCount": children})
        if infants > 0:
            passengers.append({"passengerType": 2, "passengerCount": infants})

        response = await self.api_client.pricing(
            flight_id=flight_id,
            serial_number=serial_number,
            airline=airline,
            passengers=passengers
        )

        # 解析计价结果
        detail_list = response.get("detail", [])
        if detail_list:
            first_detail = detail_list[0]
            logger.info(f"计价完成: policySerialNumber={first_detail.get('serialNumber')}")
            return first_detail

        logger.warning("计价接口返回空 detail，使用原始响应")
        return response

    async def _create_order(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """创建订单（内部步骤）

        调用 TOOrderSave 接口，使用实时航班下单模式（createOrderType=1）。
        乘客信息直接从 context["passengers"] 获取，无需预先创建出行人。
        """
        context["current_step"] = "create_order"

        policy_serial_number = context.get("policy_serial_number", "")
        logger.info(f"创建订单: policySerialNumber={policy_serial_number}")

        order_data = {
            "policySerialNumber": policy_serial_number,
            "createOrderType": context.get("create_order_type", 1),
            "isConvert": 0,
            "passengerList": context.get("passengers", []),
            "contact": context.get("contact", {})
        }

        response = await self.api_client.create_order(order_data)

        detail = response.get("detail", {})
        order_id = detail.get("orderId") if isinstance(detail, dict) else None
        logger.info(f"订单创建成功: orderId={order_id}")
        return detail if detail else response

    async def _verify_order(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """验价验舱（内部步骤）"""
        context["current_step"] = "verify_order"

        order_id = context.get("order_id")
        logger.info(f"验价验舱: orderId={order_id}")

        response = await self.api_client.verify_order(order_id)
        logger.info(f"验价验舱完成: orderId={order_id}")
        return response.get("detail", response)

    async def execute_payment_workflow(
        self,
        order_id: str,
        payment_method: str = "online"
    ) -> Dict[str, Any]:
        """执行支付工作流

        完整流程：
        1. 验价验舱（OrderPayVer）
        2. 确认支付（OrderPayConfirm）

        Args:
            order_id: 订单号
            payment_method: 支付方式（online/offline）

        Returns:
            支付结果
        """
        try:
            logger.info(f"支付工作流 - 验价验舱: orderId={order_id}")
            await self.api_client.verify_order(order_id)

            logger.info(f"支付工作流 - 确认支付: orderId={order_id}")
            pay_result = await self.api_client.confirm_pay(order_id, payment_method)

            logger.info(f"支付工作流完成: orderId={order_id}")

            return {
                "success": True,
                "order_id": order_id,
                "status": "paid",
                "message": "支付成功",
                "data": pay_result.get("detail", {})
            }

        except Exception as e:
            logger.error(f"支付工作流执行失败: {e}")
            raise WorkflowError(
                f"支付失败: {str(e)}",
                step="payment_workflow",
                details={"order_id": order_id}
            )

    async def execute_cancel_workflow(
        self,
        order_id: str,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """执行取消工作流

        Args:
            order_id: 订单号
            reason: 取消原因

        Returns:
            取消结果
        """
        try:
            logger.info(f"取消订单: orderId={order_id}")

            response = await self.api_client.cancel_order(order_id, reason)

            logger.info(f"取消成功: orderId={order_id}")

            return {
                "success": True,
                "order_id": order_id,
                "status": "cancelled",
                "message": "订单已取消",
                "data": response.get("detail", {})
            }

        except Exception as e:
            logger.error(f"取消订单失败: {e}")
            raise WorkflowError(
                f"取消失败: {str(e)}",
                step="cancel_workflow",
                details={"order_id": order_id}
            )

    async def _handle_error(self, error: Exception, context: Dict[str, Any]) -> None:
        """错误处理

        如果订单已创建，尝试自动取消以避免悬空订单。
        """
        logger.error(f"工作流错误处理: {error}")
        context["errors"].append({
            "error": str(error),
            "step": context.get("current_step", "unknown")
        })

        if context.get("order_id"):
            try:
                logger.info(f"尝试取消已创建的订单: {context['order_id']}")
                await self.api_client.cancel_order(
                    context["order_id"],
                    "工作流执行失败，自动取消"
                )
            except Exception as e:
                logger.error(f"自动取消订单失败: {e}")
