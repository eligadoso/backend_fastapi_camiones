from fastapi import APIRouter

from .auth_api import router as auth_router
from .base_api import router as webhook_router
from .operations_api import router as operations_router

router = APIRouter()
router.include_router(webhook_router)
router.include_router(auth_router)
router.include_router(operations_router)

__all__ = ["router"]
