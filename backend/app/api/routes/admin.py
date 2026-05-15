from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.core.database import get_db
from app.schemas import *
from app.services.admin_service import get_system_config
from app.services.email_service import EmailService
from app.api.deps import get_current_user, require_admin, registrar_auditoria
import json

router = APIRouter(prefix="/admin", tags=["admin"])

@router.get("/config")
async def read_config(db: AsyncSession = Depends(get_db), user: dict = Depends(require_admin)):
    return await get_system_config(db)

@router.put("/config")
async def update_config(cfg: ConfigSistemaUpdate, db: AsyncSession = Depends(get_db), user: dict = Depends(require_admin)):
    await db.execute(text("UPDATE configuracion_sistema SET sla_horas=:sla, correo_escalacion=:esc, correo_seguridad=:seg WHERE id=1"),
                     {"sla": cfg.sla_horas, "esc": cfg.correo_escalacion, "seg": cfg.correo_seguridad})
    await registrar_auditoria(db, user['id'], 'ADMIN_CRITICO', f"Actualizó configuración global del SLA por {user['nombre']}")
    return {"success": True, "message": "Configuración actualizada"}

@router.get("/reglas")
async def get_reglas(db: AsyncSession = Depends(get_db), user: dict = Depends(require_admin)):
    result = await db.execute(text("""
        SELECT r.*, p.nombre as plat_nom, s.nombre as serv_nom, tc.nombre as tipo_nom, t.nombre as terc_nom
        FROM regla_texto r
        LEFT JOIN plataforma p ON r.plataforma_id = p.id
        LEFT JOIN servicio s ON r.servicio_id = s.id
        LEFT JOIN tipo_comunicado tc ON r.tipo_comunicado_id = tc.id
        LEFT JOIN tercero t ON r.tercero_id = t.id
        WHERE r.estado = 1 ORDER BY r.fase ASC, r.id DESC
    """))
    return [dict(r) for r in result.mappings().all()]

@router.post("/reglas")
async def create_regla(regla: ReglaTextoCreate, db: AsyncSession = Depends(get_db), user: dict = Depends(require_admin)):
    await db.execute(text("""
        INSERT INTO regla_texto (plataforma_id, servicio_id, tercero_id, tipo_comunicado_id, fase, entidad_afectada, asunto_template, descripcion_template)
        VALUES (:p, :s, :t, :tc, :f, :e, :a, :d)
    """), {"p": regla.plataforma_id, "s": regla.servicio_id, "t": regla.tercero_id,
           "tc": regla.tipo_comunicado_id, "f": regla.fase, "e": regla.entidad_afectada,
           "a": regla.asunto_template, "d": regla.descripcion_template})
    await registrar_auditoria(db, user['id'], 'ADMIN_REGLAS', f"Creó regla para fase {regla.fase}")
    return {"success": True, "message": "Regla creada"}

@router.put("/reglas/{regla_id}")
async def update_regla(regla_id: int, regla: ReglaTextoCreate, db: AsyncSession = Depends(get_db), user: dict = Depends(require_admin)):
    await db.execute(text("""
        UPDATE regla_texto SET plataforma_id=:p, servicio_id=:s, tercero_id=:t, tipo_comunicado_id=:tc,
        fase=:f, entidad_afectada=:e, asunto_template=:a, descripcion_template=:d WHERE id=:id
    """), {"p": regla.plataforma_id, "s": regla.servicio_id, "t": regla.tercero_id,
           "tc": regla.tipo_comunicado_id, "f": regla.fase, "e": regla.entidad_afectada,
           "a": regla.asunto_template, "d": regla.descripcion_template, "id": regla_id})
    await registrar_auditoria(db, user['id'], 'ADMIN_REGLAS', f"Actualizó regla ID {regla_id}")
    return {"success": True, "message": "Regla actualizada"}

@router.delete("/reglas/{regla_id}")
async def delete_regla(regla_id: int, db: AsyncSession = Depends(get_db), user: dict = Depends(require_admin)):
    await db.execute(text("DELETE FROM regla_texto WHERE id = :id"), {"id": regla_id})
    await registrar_auditoria(db, user['id'], 'ADMIN_REGLAS', f"Eliminó regla ID {regla_id}")
    return {"success": True, "message": "Regla eliminada"}

@router.get("/servicios")
async def get_servicios(db: AsyncSession = Depends(get_db), user: dict = Depends(require_admin)):
    result = await db.execute(text("SELECT id, nombre, estado FROM servicio ORDER BY nombre"))
    return [dict(r) for r in result.mappings().all()]

@router.post("/servicios")
async def create_servicio(s: ServicioCreate, db: AsyncSession = Depends(get_db), user: dict = Depends(require_admin)):
    await db.execute(text("INSERT INTO servicio (nombre, estado) VALUES (:n, TRUE)"), {"n": s.nombre.upper().strip()})
    await registrar_auditoria(db, user['id'], 'ADMIN_SERVICIOS', f"Creó servicio: {s.nombre}")
    await db.commit()
    return {"success": True, "message": "Servicio creado"}

@router.put("/servicios/{serv_id}")
async def update_servicio(serv_id: int, s: ServicioCreate, estado: bool = True,
                          db: AsyncSession = Depends(get_db), user: dict = Depends(require_admin)):
    await db.execute(text("UPDATE servicio SET nombre=:n, estado=:e WHERE id=:id"),
                     {"n": s.nombre.upper().strip(), "e": estado, "id": serv_id})
    await registrar_auditoria(db, user['id'], 'ADMIN_SERVICIOS', f"Actualizó servicio ID {serv_id}")
    await db.commit()
    return {"success": True, "message": "Servicio actualizado"}

@router.get("/terceros")
async def get_terceros(db: AsyncSession = Depends(get_db), user: dict = Depends(require_admin)):
    result = await db.execute(text("SELECT id, nombre, estado FROM tercero ORDER BY nombre"))
    return [dict(r) for r in result.mappings().all()]

@router.post("/terceros")
async def create_tercero(t: TerceroCreate, db: AsyncSession = Depends(get_db), user: dict = Depends(require_admin)):
    await db.execute(text("INSERT INTO tercero (nombre, estado) VALUES (:n, TRUE)"), {"n": t.nombre.upper().strip()})
    await registrar_auditoria(db, user['id'], 'ADMIN_TERCEROS', f"Creó tercero: {t.nombre}")
    await db.commit()
    return {"success": True, "message": "Tercero creado"}

@router.put("/terceros/{terc_id}")
async def update_tercero(terc_id: int, t: TerceroCreate, estado: bool = True,
                         db: AsyncSession = Depends(get_db), user: dict = Depends(require_admin)):
    await db.execute(text("UPDATE tercero SET nombre=:n, estado=:e WHERE id=:id"),
                     {"n": t.nombre.upper().strip(), "e": estado, "id": terc_id})
    await registrar_auditoria(db, user['id'], 'ADMIN_TERCEROS', f"Actualizó tercero ID {terc_id}")
    await db.commit()
    return {"success": True, "message": "Tercero actualizado"}

@router.get("/plantillas")
async def get_plantillas(db: AsyncSession = Depends(get_db), user: dict = Depends(require_admin)):
    result = await db.execute(text("SELECT id, plataforma_id, tipo_comunicado_id, asunto, html, estado FROM plantilla WHERE estado = TRUE"))
    return [dict(r) for r in result.mappings().all()]

@router.post("/plantillas")
async def create_plantilla(p: PlantillaCreate, db: AsyncSession = Depends(get_db), user: dict = Depends(require_admin)):
    await db.execute(text("INSERT INTO plantilla (plataforma_id, tipo_comunicado_id, version, asunto, html, estado) VALUES (:p, :tc, 1, :a, :h, TRUE)"),
                     {"p": p.plataforma_id, "tc": p.tipo_comunicado_id, "a": p.asunto.strip(), "h": p.html})
    await registrar_auditoria(db, user['id'], 'ADMIN_PLANTILLAS', f"Creó plantilla: {p.asunto}")
    await db.commit()
    return {"success": True, "message": "Plantilla creada"}

@router.put("/plantillas/{plant_id}")
async def update_plantilla(plant_id: int, p: PlantillaCreate, estado: bool = True,
                           db: AsyncSession = Depends(get_db), user: dict = Depends(require_admin)):
    await db.execute(text("UPDATE plantilla SET asunto=:a, html=:h, estado=:e WHERE id=:id"),
                     {"a": p.asunto.strip(), "h": p.html, "e": estado, "id": plant_id})
    await registrar_auditoria(db, user['id'], 'ADMIN_PLANTILLAS', f"Actualizó plantilla ID {plant_id}")
    await db.commit()
    return {"success": True, "message": "Plantilla actualizada"}

@router.get("/usuarios")
async def get_usuarios(db: AsyncSession = Depends(get_db), user: dict = Depends(require_admin)):
    result = await db.execute(text("SELECT id, nombre, apellido, correo, rol, estado FROM analista"))
    return [dict(r) for r in result.mappings().all()]

@router.post("/usuarios")
async def create_usuario(u: UsuarioCreate, db: AsyncSession = Depends(get_db), user: dict = Depends(require_admin)):
    from app.core.security import hash_password
    await db.execute(text("INSERT INTO analista (nombre, apellido, correo, password, rol, estado) VALUES (:n, :a, :c, :p, :r, TRUE)"),
                     {"n": u.nombre.strip(), "a": u.apellido.strip(), "c": u.correo.strip().lower(),
                      "p": hash_password(u.password), "r": u.rol})
    await registrar_auditoria(db, user['id'], 'ADMIN_USUARIO', f"Creó usuario: {u.correo}")
    await db.commit()
    return {"success": True, "message": "Usuario creado"}

@router.put("/usuarios/{user_id}")
async def update_usuario(user_id: int, u: UsuarioUpdate, db: AsyncSession = Depends(get_db), user: dict = Depends(require_admin)):
    from app.core.security import hash_password
    fields = []
    params = {"id": user_id}
    if u.nombre is not None: fields.append("nombre=:n"); params["n"] = u.nombre.strip()
    if u.apellido is not None: fields.append("apellido=:a"); params["a"] = u.apellido.strip()
    if u.correo is not None: fields.append("correo=:c"); params["c"] = u.correo.strip().lower()
    if u.password: fields.append("password=:p"); params["p"] = hash_password(u.password)
    if u.rol is not None: fields.append("rol=:r"); params["r"] = u.rol
    if u.estado is not None: fields.append("estado=:e"); params["e"] = u.estado
    if fields:
        await db.execute(text(f"UPDATE analista SET {', '.join(fields)} WHERE id=:id"), params)
        await registrar_auditoria(db, user['id'], 'ADMIN_USUARIO', f"Actualizó usuario ID {user_id}")
        await db.commit()
    return {"success": True, "message": "Usuario actualizado"}

@router.get("/roles")
async def get_roles(db: AsyncSession = Depends(get_db), user: dict = Depends(require_admin)):
    result = await db.execute(text("SELECT DISTINCT rol FROM analista"))
    roles = [r['rol'] for r in result.mappings().all()]
    return list(set(roles + ["Administrador", "Lider", "Monitoreo", "Corporate"]))

@router.get("/roles/{rol}")
async def get_rol_permisos(rol: str, db: AsyncSession = Depends(get_db), user: dict = Depends(require_admin)):
    r = await db.execute(text("SELECT * FROM rol_permisos WHERE LOWER(rol_nombre) = LOWER(:rol)"), {"rol": rol})
    permisos = r.mappings().first()
    r2 = await db.execute(text("SELECT servicio_id FROM rol_servicios WHERE LOWER(rol_nombre) = LOWER(:rol)"), {"rol": rol})
    servicios = [row['servicio_id'] for row in r2.mappings().all()]
    return {"permisos": dict(permisos) if permisos else {}, "servicios_restringidos": servicios}

@router.put("/roles/{rol}")
async def update_rol_permisos(rol: str, p: PermisosUpdate, db: AsyncSession = Depends(get_db), user: dict = Depends(require_admin)):
    existing = await db.execute(text("SELECT rol_nombre FROM rol_permisos WHERE LOWER(rol_nombre) = LOWER(:rol)"), {"rol": rol})
    if existing.mappings().first():
        await db.execute(text("""UPDATE rol_permisos SET ver_aprobaciones=:v1, ver_apertura=:v2, ver_cierre=:v3,
            ver_mantenimiento=:v4, ver_edicion=:v5, ver_reportes=:v6, ver_admin=:v7, puede_aprobar=:v8,
            ver_solo_propios=:v9, exige_aprobacion=:v10 WHERE LOWER(rol_nombre)=LOWER(:rol)"""),
            {"v1": p.ver_aprobaciones, "v2": p.ver_apertura, "v3": p.ver_cierre, "v4": p.ver_mantenimiento,
             "v5": p.ver_edicion, "v6": p.ver_reportes, "v7": p.ver_admin, "v8": p.puede_aprobar,
             "v9": p.ver_solo_propios, "v10": p.exige_aprobacion, "rol": rol})
    else:
        await db.execute(text("""INSERT INTO rol_permisos (rol_nombre, ver_aprobaciones, ver_apertura, ver_cierre,
            ver_mantenimiento, ver_edicion, ver_reportes, ver_admin, puede_aprobar, ver_solo_propios, exige_aprobacion)
            VALUES (:rol,:v1,:v2,:v3,:v4,:v5,:v6,:v7,:v8,:v9,:v10)"""),
            {"rol": rol.capitalize(), "v1": p.ver_aprobaciones, "v2": p.ver_apertura, "v3": p.ver_cierre,
             "v4": p.ver_mantenimiento, "v5": p.ver_edicion, "v6": p.ver_reportes, "v7": p.ver_admin,
             "v8": p.puede_aprobar, "v9": p.ver_solo_propios, "v10": p.exige_aprobacion})
    await db.execute(text("DELETE FROM rol_servicios WHERE LOWER(rol_nombre) = LOWER(:rol)"), {"rol": rol})
    for sid in p.servicios_restringidos:
        await db.execute(text("INSERT INTO rol_servicios (rol_nombre, servicio_id) VALUES (:rol, :sid)"),
                        {"rol": rol.capitalize(), "sid": sid})
    await registrar_auditoria(db, user['id'], 'ADMIN_RBAC', f"Actualizó configuración de rol: {rol}")
    await db.commit()
    return {"success": True, "message": "Permisos actualizados"}

@router.get("/auditoria")
async def get_auditoria(db: AsyncSession = Depends(get_db), user: dict = Depends(require_admin)):
    result = await db.execute(text("""
        SELECT al.fecha, an.nombre as analista, al.accion, al.detalles
        FROM audit_log al LEFT JOIN analista an ON al.analista_id = an.id
        ORDER BY al.id DESC LIMIT 200
    """))
    return [dict(r, fecha=str(r['fecha'])) for r in result.mappings().all()]

@router.get("/correos-internos")
async def get_correos_internos(db: AsyncSession = Depends(get_db), user: dict = Depends(require_admin)):
    result = await db.execute(text("SELECT id, email, estado FROM correo_interno_cc"))
    return [dict(r) for r in result.mappings().all()]

@router.post("/correos-internos")
async def create_correos_internos(c: CorreoInternoCreate, db: AsyncSession = Depends(get_db), user: dict = Depends(require_admin)):
    for em in [e.strip().lower() for e in c.emails.replace('\n', ',').split(',') if e.strip()]:
        await db.execute(text("INSERT INTO correo_interno_cc (email, estado) VALUES (:e, TRUE)"), {"e": em})
    await registrar_auditoria(db, user['id'], 'ADMIN_CORREOS', "Agregó correos internos")
    await db.commit()
    return {"success": True, "message": "Correos guardados"}

@router.delete("/correos-internos/{correo_id}")
async def delete_correo_interno(correo_id: int, db: AsyncSession = Depends(get_db), user: dict = Depends(require_admin)):
    await db.execute(text("DELETE FROM correo_interno_cc WHERE id = :id"), {"id": correo_id})
    await registrar_auditoria(db, user['id'], 'ADMIN_CORREOS', f"Eliminó correo interno ID {correo_id}")
    await db.commit()
    return {"success": True, "message": "Correo eliminado"}

@router.get("/correos-servicio/{servicio_id}")
async def get_correos_servicio(servicio_id: int, db: AsyncSession = Depends(get_db), user: dict = Depends(require_admin)):
    result = await db.execute(text("""
        SELECT sc.*, p.nombre as plataforma_nom, t.nombre as tercero_nom
        FROM servicio_correo sc
        LEFT JOIN plataforma p ON sc.plataforma_id = p.id
        LEFT JOIN tercero t ON sc.tercero_id = t.id
        WHERE sc.servicio_id = :sid
    """), {"sid": servicio_id})
    return [dict(r) for r in result.mappings().all()]

@router.post("/correos-servicio")
async def create_correo_servicio(c: ServicioCorreoCreate, db: AsyncSession = Depends(get_db), user: dict = Depends(require_admin)):
    await db.execute(text("""INSERT INTO servicio_correo (servicio_id, nombre, email, estado, plataforma_id, tercero_id)
        VALUES (:sid, :nom, :em, TRUE, :pid, :tid)"""),
        {"sid": c.servicio_id, "nom": c.nombre, "em": c.email, "pid": c.plataforma_id, "tid": c.tercero_id})
    await registrar_auditoria(db, user['id'], 'ADMIN_CORREOS', f"Agregó correo a servicio {c.servicio_id}")
    await db.commit()
    return {"success": True, "message": "Correo agregado"}

@router.delete("/correos-servicio/{correo_id}")
async def delete_correo_servicio(correo_id: int, db: AsyncSession = Depends(get_db), user: dict = Depends(require_admin)):
    await db.execute(text("DELETE FROM servicio_correo WHERE id = :id"), {"id": correo_id})
    await registrar_auditoria(db, user['id'], 'ADMIN_CORREOS', f"Eliminó correo servicio ID {correo_id}")
    await db.commit()
    return {"success": True, "message": "Correo eliminado"}



@router.get("/vinculos")
async def get_vinculos(db: AsyncSession = Depends(get_db), user: dict = Depends(require_admin)):
    result = await db.execute(text("""
        SELECT st.*, s.nombre as servicio_nom, t.nombre as tercero_nom
        FROM servicio_tercero st
        JOIN servicio s ON st.servicio_id = s.id
        JOIN tercero t ON st.tercero_id = t.id
        ORDER BY s.nombre, t.nombre
    """))
    return [dict(r) for r in result.mappings().all()]

@router.post("/vinculos")
async def create_vinculo(body: dict, db: AsyncSession = Depends(get_db), user: dict = Depends(require_admin)):
    servicio_id = body.get("servicio_id")
    tercero_id = body.get("tercero_id")
    if not servicio_id or not tercero_id:
        raise HTTPException(status_code=400, detail="servicio_id y tercero_id requeridos")
    existing = await db.execute(
        text("SELECT id FROM servicio_tercero WHERE servicio_id = :sid AND tercero_id = :tid"),
        {"sid": servicio_id, "tid": tercero_id}
    )
    if existing.mappings().first():
        raise HTTPException(status_code=400, detail="El vínculo ya existe")
    await db.execute(
        text("INSERT INTO servicio_tercero (servicio_id, tercero_id) VALUES (:sid, :tid)"),
        {"sid": servicio_id, "tid": tercero_id}
    )
    await registrar_auditoria(db, user['id'], 'ADMIN_VINCULOS', f"Vincularon servicio {servicio_id} con tercero {tercero_id}")
    await db.commit()
    return {"success": True, "message": "Vínculo creado"}

@router.delete("/vinculos/{vinculo_id}")
async def delete_vinculo(vinculo_id: int, db: AsyncSession = Depends(get_db), user: dict = Depends(require_admin)):
    await db.execute(text("DELETE FROM servicio_tercero WHERE id = :id"), {"id": vinculo_id})
    await registrar_auditoria(db, user['id'], 'ADMIN_VINCULOS', f"Eliminaron vínculo ID {vinculo_id}")
    await db.commit()
    return {"success": True, "message": "Vínculo eliminado"}
