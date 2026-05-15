from fastapi import Header, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.core.database import get_db
from app.core.security import decode_access_token
from typing import Optional, List

async def get_current_user(authorization: str = Header(...), db: AsyncSession = Depends(get_db)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token requerido")
    payload = decode_access_token(authorization[7:])
    if not payload:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")
    result = await db.execute(
        text("SELECT id, nombre, apellido, correo, rol, estado FROM analista WHERE id = :id"),
        {"id": int(payload["sub"])}
    )
    user = result.mappings().first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if not user["estado"]:
        raise HTTPException(status_code=403, detail="Usuario inactivo. Contacte al administrador.")
    return dict(user)

BOOLEAN_FIELDS = {"ver_aprobaciones", "ver_apertura", "ver_cierre", "ver_mantenimiento",
                   "ver_edicion", "ver_reportes", "ver_admin", "puede_aprobar",
                   "ver_solo_propios", "exige_aprobacion"}

async def get_permisos_usuario(db: AsyncSession, rol: str) -> dict:
    result = await db.execute(
        text("SELECT * FROM rol_permisos WHERE LOWER(rol_nombre) = LOWER(:rol)"),
        {"rol": rol}
    )
    permisos = result.mappings().first()
    if permisos:
        raw = dict(permisos)
        return {k: bool(v) if k in BOOLEAN_FIELDS else v for k, v in raw.items()}
    rol_lower = rol.lower()
    defaults = {
        "ver_aprobaciones": False, "ver_apertura": True, "ver_cierre": True,
        "ver_mantenimiento": True, "ver_edicion": False, "ver_reportes": False,
        "ver_admin": False, "puede_aprobar": False, "ver_solo_propios": False,
        "exige_aprobacion": True
    }
    if rol_lower == "administrador":
        defaults.update({"ver_aprobaciones": True, "ver_edicion": True, "ver_reportes": True, "ver_admin": True, "puede_aprobar": True, "exige_aprobacion": False})
    elif rol_lower == "lider":
        defaults.update({"ver_aprobaciones": True, "ver_edicion": True, "ver_reportes": True, "puede_aprobar": True, "exige_aprobacion": False})
    elif rol_lower == "corporate":
        defaults.update({"ver_aprobaciones": False, "ver_apertura": False, "ver_cierre": False, "ver_mantenimiento": False, "ver_edicion": False, "ver_reportes": True, "ver_admin": False, "puede_aprobar": False, "ver_solo_propios": False, "exige_aprobacion": False})
    return defaults

async def get_servicios_restringidos(db: AsyncSession, rol: str) -> List[int]:
    result = await db.execute(
        text("SELECT servicio_id FROM rol_servicios WHERE LOWER(rol_nombre) = LOWER(:rol)"),
        {"rol": rol}
    )
    return [r["servicio_id"] for r in result.mappings().all()]

async def require_permiso(permiso: str, user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    permisos = await get_permisos_usuario(db, user["rol"])
    if not permisos.get(permiso, False):
        raise HTTPException(status_code=403, detail=f"Acceso denegado. No tienes permiso: {permiso}")
    return user

async def require_admin(user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await require_permiso("ver_admin", user, db)

async def registrar_auditoria(db: AsyncSession, analista_id, accion: str, detalles: str):
    await db.execute(
        text("INSERT INTO audit_log (analista_id, accion, detalles) VALUES (:aid, :acc, :det)"),
        {"aid": analista_id, "acc": accion, "det": detalles}
    )
    await db.commit()
