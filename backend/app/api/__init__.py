from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.api.routes.auth import router as auth_router
from app.api.routes.comunicados import router as comunicados_router
from app.api.routes.admin import router as admin_router
from app.api.routes.reportes import router as reportes_router
