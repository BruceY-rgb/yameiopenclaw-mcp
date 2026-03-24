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
    - 预订工作流（查询→计价→创建出行人→生单→验价验舱）
    - 支付工作流（验价验舱→确认支付）
    - 取消工作流（取消订单）
    """

    def __init__(
        self,
        api_client: MeiyaApiClient,
        auth_manager: Optional[AuthManager] = None
    ):
        """初始化工作流编排器

        Args:
            api_client: API客户端实例
            auth_manager: 认证管理器实例（可选）
        """
        self.api_client = api_client
        self.auth_manager = auth_manager

    async def execute_booking_workflow(
        self,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """执行预订工作流

        完整流程：
        1. 查询航班
        2. 计价
        3. 创建出行人
        4. 生单
        5. 验价验舱

        Args:
            context: 工作流上下文，包含：
                - origin: 出发地
                - destination: 目的地
                - departure_date: 出发日期
                - flight_id: 航班ID（可选，如果不提供则先查询）
                - passengers: 乘客列表
                - contact: 联系人信息
                - cabin_class: 舱位等级

        Returns:
            工作流执行结果
        """
        workflow_context = {
            **context,
            "steps_completed": [],
            "errors": []
        }

        try:
            # 步骤1: 如果没有提供flight_id，先查询航班
            if "flight_id" not in context or not context["flight_id"]:
                flights = await self._search_flights(workflow_context)
                if not flights:
                    raise WorkflowError("未找到可用航班", step="search_flights")
                workflow_context["flight_id"] = flights[0].get("flightId")
                workflow_context["flights"] = flights

            # 步骤2: 计价
            pricing = await self._pricing(workflow_context)
            workflow_context["pricing"] = pricing
            workflow_context["policy_serial_number"] = pricing.get("policySerialNumber")

            # 步骤3: 创建出行人
            passengers = await self._create_passengers(workflow_context)
            workflow_context["passengers"] = passengers
            workflow_context["passenger_ids"] = [p.get("passengerId") for p in passengers]

            # 步骤4: 生单
            order = await self._create_order(workflow_context)
            workflow_context["order_id"] = order.get("orderId")
            workflow_context["order"] = order

            # 步骤5: 验价验舱
            verify_result = await self._verify_order(workflow_context)
            workflow_context["verify_result"] = verify_result

            workflow_context["steps_completed"] = [
                "search_flights",
                "pricing",
                "create_passengers",
                "create_order",
                "verify_order"
            ]

            logger.info(f"预订工作流完成: order_id={workflow_context.get('order_id')}")

            return {
                "success": True,
                "order_id": workflow_context.get("order_id"),
                "status": order.get("status", "created"),
                "total_amount": order.get("totalAmount"),
                "currency": order.get("currency", "CNY"),
                "payment_url": order.get("paymentUrl"),
                "pnr": order.get("pnr"),
                "message": "预订成功"
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
        """查询航班"""
        context["current_step"] = "search_flights"

        logger.info(f"查询航班: {context.get('origin')} -> {context.get('destination')}")

        response = await self.api_client.search_flights(
            origin=context["origin"],
            destination=context["destination"],
            departure_date=context["departure_date"],
            adults=context.get("adults", 1),
            children=context.get("children", 0),
            infants=context.get("infants", 0),
            cabin_class=context.get("cabin_class", "economy"),
            trip_type=context.get("trip_type", "one_way"),
            return_date=context.get("return_date")
        )

        data = response.get("data", {})
        flights = data.get("flights", [])

        logger.info(f"查询到 {len(flights)} 个航班")
        return flights

    async def _pricing(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """航班计价"""
        context["current_step"] = "pricing"

        logger.info(f"计价: flight_id={context.get('flight_id')}")

        passengers = context.get("passengers_info", {"adults": 1, "children": 0, "infants": 0})

        response = await self.api_client.pricing(
            flight_id=context["flight_id"],
            cabin_class=context.get("cabin_class", "economy"),
            passengers=passengers
        )

        data = response.get("data", {})
        logger.info(f"计价完成: policy_serial_number={data.get('policySerialNumber')}")
        return data

    async def _create_passengers(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """创建出行人"""
        context["current_step"] = "create_passengers"

        passengers_data = context.get("passengers", [])
        created_passengers = []

        for pax in passengers_data:
            logger.info(f"创建出行人: {pax.get('name')}")

            # 如果已经有passenger_id，直接使用
            if "passengerId" in pax:
                created_passengers.append(pax)
                continue

            response = await self.api_client.create_passenger(pax)
            created_passenger = response.get("data", {})
            created_passengers.append(created_passenger)

        logger.info(f"创建了 {len(created_passengers)} 个出行人")
        return created_passengers

    async def _create_order(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """创建订单"""
        context["current_step"] = "create_order"

        logger.info(f"创建订单: flight_id={context.get('flight_id')}")

        passengers = context.get("passengers", [])
        contact = context.get("contact", {})

        order_data = {
            "policySerialNumber": context.get("policy_serial_number"),
            "createOrderType": context.get("create_order_type", 1),  # 1=实时航班
            "passengerList": passengers,
            "contact": contact
        }

        # 添加航班信息
        if "flight_id" in context:
            order_data["flightId"] = context["flight_id"]

        response = await self.api_client.create_order(order_data)

        data = response.get("data", {})
        logger.info(f"订单创建成功: order_id={data.get('orderId')}")
        return data

    async def _verify_order(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """验价验舱"""
        context["current_step"] = "verify_order"

        order_id = context.get("order_id")
        logger.info(f"验价验舱: order_id={order_id}")

        response = await self.api_client.verify_order(order_id)

        logger.info(f"验价验舱完成: order_id={order_id}")
        return response.get("data", {})

    async def execute_payment_workflow(
        self,
        order_id: str,
        payment_method: str = "online"
    ) -> Dict[str, Any]:
        """执行支付工作流

        完整流程：
        1. 验价验舱
        2. 确认支付

        Args:
            order_id: 订单ID
            payment_method: 支付方式

        Returns:
            支付结果
        """
        try:
            # 步骤1: 验价验舱
            logger.info(f"支付工作流 - 验价验舱: order_id={order_id}")
            verify_result = await self.api_client.verify_order(order_id)

            # 步骤2: 确认支付
            logger.info(f"支付工作流 - 确认支付: order_id={order_id}")
            pay_result = await self.api_client.confirm_pay(order_id, payment_method)

            logger.info(f"支付工作流完成: order_id={order_id}")

            return {
                "success": True,
                "order_id": order_id,
                "status": "paid",
                "message": "支付成功",
                "data": pay_result.get("data", {})
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
            order_id: 订单ID
            reason: 取消原因

        Returns:
            取消结果
        """
        try:
            logger.info(f"取消订单: order_id={order_id}")

            response = await self.api_client.cancel_order(order_id, reason)

            logger.info(f"取消成功: order_id={order_id}")

            return {
                "success": True,
                "order_id": order_id,
                "status": "cancelled",
                "message": "订单已取消",
                "data": response.get("data", {})
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

        可以在这里实现补偿事务逻辑，如：
        - 取消已创建的订单
        - 删除已创建的出行人
        """
        logger.error(f"工作流错误处理: {error}")
        context["errors"].append({
            "error": str(error),
            "step": context.get("current_step", "unknown")
        })

        # 如果订单已创建，尝试取消
        if "order_id" in context and context.get("order_id"):
            try:
                logger.info(f"尝试取消已创建的订单: {context['order_id']}")
                await self.api_client.cancel_order(
                    context["order_id"],
                    "工作流执行失败，自动取消"
                )
            except Exception as e:
                logger.error(f"自动取消订单失败: {e}")
