from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from app.core.config import settings
from app.api.routes.auth import router as auth_router
from app.api.routes.comunicados import router as comunicados_router
from app.api.routes.admin import router as admin_router
from app.api.routes.reportes import router as reportes_router
import asyncio
import logging

logger = logging.getLogger(__name__)

SLA_CHECK_INTERVAL_SECONDS = 300  # 5 minutos

async def sla_background_task():
    while True:
        try:
            from app.core.database import async_session_factory
            from app.services.sla_service import revisar_y_escalar_slas
            async with async_session_factory() as db:
                await revisar_y_escalar_slas(db)
            logger.info("Verificación SLA completada en background")
        except Exception as e:
            logger.error(f"Error en verificación SLA background: {e}", exc_info=True)
        await asyncio.sleep(SLA_CHECK_INTERVAL_SECONDS)

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(sla_background_task())
    logger.info(f"Background SLA check iniciado (cada {SLA_CHECK_INTERVAL_SECONDS}s)")
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    logger.info("Background SLA check detenido")

app = FastAPI(
    title="Portal de Comunicados TI - API",
    version="2.0.0",
    description="Backend API para gesti\u00f3n de comunicados de novedades TI",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Error global: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": f"Error interno del servidor: {str(exc)}"},
        headers={"Access-Control-Allow-Origin": "*"}
    )

app.include_router(auth_router)
app.include_router(comunicados_router)
app.include_router(admin_router)
app.include_router(reportes_router)

@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.0.0"}
