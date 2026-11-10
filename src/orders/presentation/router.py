from uuid import UUID

from fastapi import APIRouter, Depends, Query

from orders.application.service import OrderService
from orders.presentation.dependencies import get_order_service
from orders.presentation.schemas import OrderCreate, OrderResponse
from user.presentation.dependencies import get_current_user

router = APIRouter(prefix="/orders", tags=["Orders"])


@router.post("", response_model=OrderResponse, status_code=201)
async def create_order(data: OrderCreate, user=Depends(get_current_user),
                       service: OrderService = Depends(get_order_service)):
    return await service.create_order(user.id, [item.model_dump() for item in data.items])


@router.get("", response_model=list[OrderResponse])
async def list_orders(offset: int = Query(0, ge=0, le=100_000_000), limit: int = Query(20, ge=1, le=100),
                      user=Depends(get_current_user), service: OrderService = Depends(get_order_service)):
    return await service.list_orders(user.id, offset, limit)


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(order_id: UUID, user=Depends(get_current_user),
                    service: OrderService = Depends(get_order_service)):
    return await service.get_order(order_id, user.id, user.role)


@router.post("/{order_id}/cancel", response_model=OrderResponse)
async def cancel_order(order_id: UUID, user=Depends(get_current_user),
                       service: OrderService = Depends(get_order_service)):
    return await service.cancel_order(order_id, user.id, user.role)
