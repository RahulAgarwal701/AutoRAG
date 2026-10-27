from fastapi import APIRouter

from app.api.routes.agents import router as agents_router
from app.api.routes.api_keys import router as api_keys_router
from app.api.routes.auth import router as auth_router
from app.api.routes.chat import router as chat_router
from app.api.routes.documents import router as documents_router
from app.api.routes.evaluations import router as evaluations_router
from app.api.routes.health import router as health_router
from app.api.routes.metrics import router as metrics_router
from app.api.routes.public import router as public_router
from app.api.routes.usage import router as usage_router
from app.api.routes.widget_policy import router as widget_policy_router
from app.core.config import get_settings

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(metrics_router)
api_router.include_router(widget_policy_router)
api_router.include_router(public_router)

protected_api_router = APIRouter(prefix=get_settings().api_v1_prefix)
protected_api_router.include_router(auth_router)
protected_api_router.include_router(agents_router)
protected_api_router.include_router(documents_router)
protected_api_router.include_router(evaluations_router)
protected_api_router.include_router(api_keys_router)
protected_api_router.include_router(chat_router)
protected_api_router.include_router(usage_router)
api_router.include_router(protected_api_router)
