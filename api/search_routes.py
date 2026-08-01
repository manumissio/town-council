from fastapi import APIRouter

from api.search_read_routes import router as search_read_router
from api.search_semantic_routes import router as search_semantic_router
from api.trends_routes import router as trends_router

router = APIRouter()
router.include_router(search_read_router)
router.include_router(search_semantic_router)
router.include_router(trends_router)
