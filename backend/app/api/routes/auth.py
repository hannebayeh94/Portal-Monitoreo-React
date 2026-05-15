from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.core.database import get_db
from app.core.security import verify_password, create_access_token, decode_access_token
from app.schemas import LoginRequest, TokenResponse, UserInfo
from app.api.deps import get_permisos_usuario, get_servicios_restringidos

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/login")
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        text("SELECT id, nombre, apellido, correo, password, rol FROM analista WHERE correo = :correo AND estado = TRUE"),
        {"correo": req.correo}
    )
    user = result.mappings().first()
    if not user or not verify_password(req.password, user['password']):
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")

    user_info = UserInfo(id=user['id'], nombre=user['nombre'], apellido=user['apellido'],
                         correo=user['correo'], rol=user['rol'])
    token = create_access_token({"sub": str(user['id']), "rol": user['rol']})

    await db.execute(
        text("INSERT INTO audit_log (analista_id, accion, detalles) VALUES (:aid, 'LOGIN', 'Inicio de sesión exitoso')"),
        {"aid": user['id']}
    )
    await db.commit()

    permisos = await get_permisos_usuario(db, user['rol'])
    servicios_rest = await get_servicios_restringidos(db, user['rol'])

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user_info.id,
            "nombre": user_info.nombre,
            "apellido": user_info.apellido,
            "correo": user_info.correo,
            "rol": user_info.rol,
            "estado": True
        },
        "permisos": permisos,
        "servicios_restringidos": servicios_rest
    }

@router.get("/me")
async def get_me(authorization: str = Header(default=""), db: AsyncSession = Depends(get_db)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token requerido")
    token = authorization[7:]
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token inválido")
    result = await db.execute(
        text("SELECT id, nombre, apellido, correo, rol, estado FROM analista WHERE id = :id"),
        {"id": int(payload['sub'])}
    )
    user = result.mappings().first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if not user["estado"]:
        raise HTTPException(status_code=403, detail="Usuario inactivo")

    permisos = await get_permisos_usuario(db, user['rol'])
    servicios_rest = await get_servicios_restringidos(db, user['rol'])

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": dict(user),
        "permisos": permisos,
        "servicios_restringidos": servicios_rest
    }
