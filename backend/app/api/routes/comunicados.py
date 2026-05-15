from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Optional
from app.core.database import get_db
from app.api.deps import get_current_user, registrar_auditoria, get_permisos_usuario, get_servicios_restringidos
from app.services import evaluar_regla, format_seguro, formatear_fecha_es, calcular_tiempo_transcurrido, calcular_estado_sla, obtener_correos_cc
from app.services.email_service import EmailService
from app.services.sla_service import revisar_y_escalar_slas
from app.core.config import settings
from jinja2 import Template
import json
import datetime
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/comunicados", tags=["comunicados"])

def _convert_datetime(val):
    if isinstance(val, str) and "T" in val:
        try:
            return val.replace("T", " ").split(".")[0].replace("Z", "")
        except:
            pass
    return val

async def _build_filtros_restriccion(db: AsyncSession, user: dict, alias: str = "c") -> tuple:
    servicios_rest = await get_servicios_restringidos(db, user["rol"])
    permisos = await get_permisos_usuario(db, user["rol"])
    where_parts = []
    params: dict = {}
    if servicios_rest:
        placeholders = ",".join([f":rs{i}" for i in range(len(servicios_rest))])
        where_parts.append(f"{alias}.servicio_id IN ({placeholders})")
        for i, sid in enumerate(servicios_rest):
            params[f"rs{i}"] = sid
    if permisos.get("ver_solo_propios"):
        where_parts.append(f"{alias}.analista_id = :uid")
        params["uid"] = user["id"]
    return where_parts, params

# ─────────────────────────────────────────────
# CATALOGOS AUXILIARES
# ─────────────────────────────────────────────

@router.get("/catalogos")
async def get_catalogos(db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    analistas = (await db.execute(text("SELECT id, nombre, apellido FROM analista WHERE estado = TRUE"))).mappings().all()
    plataformas = (await db.execute(text("SELECT id, nombre FROM plataforma WHERE estado = TRUE"))).mappings().all()
    tipos = (await db.execute(text("SELECT id, nombre, serie_id FROM tipo_comunicado WHERE estado = TRUE"))).mappings().all()
    servicios = (await db.execute(text("SELECT id, nombre FROM servicio WHERE estado = TRUE ORDER BY nombre"))).mappings().all()
    plantillas = (await db.execute(text("SELECT id, plataforma_id, tipo_comunicado_id, asunto, html, estado FROM plantilla WHERE estado = TRUE"))).mappings().all()
    return {
        "analistas": [dict(r) for r in analistas],
        "plataformas": [dict(r) for r in plataformas],
        "tipos": [dict(r) for r in tipos],
        "servicios": [dict(r) for r in servicios],
        "plantillas": [dict(r) for r in plantillas]
    }

@router.get("/terceros-por-servicio/{servicio_id}")
async def get_terceros_por_servicio(servicio_id: int, db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    result = await db.execute(
        text("SELECT t.id, t.nombre FROM servicio_tercero st JOIN tercero t ON st.tercero_id = t.id WHERE st.servicio_id = :sid AND t.estado = TRUE"),
        {"sid": servicio_id}
    )
    return [dict(r) for r in result.mappings().all()]

@router.get("/correos-segmentados")
async def get_correos_segmentados(
    servicio_id: int, plataforma_id: int,
    nombre_servicio: str = "", nombre_plataforma: str = "",
    db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)
):
    if nombre_plataforma.upper() == "GENERAL":
        result = await db.execute(text("SELECT DISTINCT email FROM servicio_correo WHERE estado = TRUE"))
    elif nombre_servicio.upper() == nombre_plataforma.upper():
        result = await db.execute(text("SELECT DISTINCT email FROM servicio_correo WHERE plataforma_id = :pid AND estado = TRUE"), {"pid": plataforma_id})
    else:
        result = await db.execute(text("SELECT DISTINCT email FROM servicio_correo WHERE servicio_id = :sid AND estado = TRUE"), {"sid": servicio_id})
    return [r["email"] for r in result.mappings().all()]

@router.get("/siguiente-consecutivo/{serie_id}")
async def get_siguiente_consecutivo(serie_id: int, db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    result = await db.execute(
        text("SELECT s.codigo, c.siguiente_valor FROM consecutivo_serie c JOIN serie s ON c.serie_id = s.id WHERE s.id = :sid"),
        {"sid": serie_id}
    )
    row = result.mappings().first()
    if not row:
        return {"codigo": "N/A", "siguiente_valor": 0, "preview": "N/A-0"}
    return {"codigo": row["codigo"], "siguiente_valor": row["siguiente_valor"], "preview": f"{row['codigo']}-{row['siguiente_valor']}"}

@router.get("/plantillas-por-tipo")
async def get_plantillas_por_tipo(
    tipo_comunicado_id: int, plataforma_id: Optional[int] = None,
    keyword: Optional[str] = None,
    db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)
):
    query = "SELECT id, plataforma_id, tipo_comunicado_id, asunto, html, estado FROM plantilla WHERE tipo_comunicado_id = :tcid AND estado = TRUE"
    params = {"tcid": tipo_comunicado_id}
    if plataforma_id:
        query += " AND (plataforma_id = :pid OR plataforma_id IS NULL)"
        params["pid"] = plataforma_id
    result = await db.execute(text(query), params)
    plantillas = [dict(r) for r in result.mappings().all()]
    if keyword:
        kws = [kw.strip().lower().replace(" ", "") for kw in keyword.split(",") if kw.strip()]
        if kws:
            plantillas = [p for p in plantillas if any(kw in p["asunto"].lower().replace(" ", "") for kw in kws)] or plantillas
    return plantillas

@router.get("/correos-internos-cc")
async def get_correos_internos_cc(db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    result = await db.execute(text("SELECT email FROM correo_interno_cc WHERE estado = TRUE"))
    return [r["email"] for r in result.mappings().all()]

# ─────────────────────────────────────────────
# APERTURA DE NOVEDAD
# ─────────────────────────────────────────────

@router.post("/apertura")
async def crear_apertura(
    body: dict,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    db_data = body.get("db_data", {})
    preview = body.get("preview", {})

    try:
        row = (await db.execute(
            text("SELECT c.siguiente_valor, s.codigo FROM consecutivo_serie c JOIN serie s ON c.serie_id = s.id WHERE c.serie_id = :sid FOR UPDATE"),
            {"sid": db_data["serie_id"]}
        )).mappings().first()
        if not row:
            raise HTTPException(status_code=400, detail="Serie inválida")

        consecutivo_real = f"{row['codigo']}-{row['siguiente_valor']}"
        await db.execute(text("UPDATE consecutivo_serie SET siguiente_valor = siguiente_valor + 1 WHERE serie_id = :sid"), {"sid": db_data["serie_id"]})

        asunto_final = db_data.get("asunto_ui", "").replace(db_data.get("consecutivo_preview", ""), consecutivo_real)
        template_html = preview.get("template_html", "")
        template_args = preview.get("template_args", {})
        template_args["consecutivo"] = consecutivo_real
        html_final = Template(template_html).render(**template_args)

        requiere_ap = db_data.get("requiere_aprobacion", False)
        estado_inicial = "Pendiente Apertura" if requiere_ap else "Abierto"
        es_externa = db_data.get("es_externa", True)

        await db.execute(text("""
            INSERT INTO comunicado (plataforma_id, tipo_comunicado_id, serie_id, consecutivo_num,
                asunto_final, html_final, descripcion, afectacion, analista_id, servicio_id,
                estado, fecha_creacion, requiere_aprobacion)
            VALUES (:p, :tc, :s, :c, :a, :h, :d, :af, :an, :sv, :es, :fc, :ra)
        """), {
            "p": db_data.get("plataforma_id"), "tc": db_data.get("tipo_comunicado_id"),
            "s": db_data["serie_id"], "c": consecutivo_real, "a": asunto_final,
            "h": html_final, "d": db_data.get("descripcion"), "af": db_data.get("afectacion"),
            "an": db_data.get("analista_id"), "sv": db_data.get("servicio_id"),
            "es": estado_inicial, "fc": _convert_datetime(db_data.get("fecha_creacion", datetime.datetime.utcnow())),
            "ra": requiere_ap
        })

        comunicado_id = (await db.execute(text("SELECT LAST_INSERT_ID() as id"))).mappings().first()["id"]

        correos_input = db_data.get("correos_input", "")
        correos_lista = [e.strip() for e in correos_input.split(",") if e.strip()]
        await db.execute(text("""
            INSERT INTO comunicado_destinatario (comunicado_id, tercero_id, email, estado, detalle)
            VALUES (:cid, :tid, :em, :est, :det)
        """), {
            "cid": comunicado_id, "tid": db_data.get("tercero_id"),
            "em": json.dumps(correos_lista),
            "est": "Pendiente" if requiere_ap else "Enviado",
            "det": db_data.get("diagnostico_falla", "")
        })

        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en apertura BD: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

    msg_correo = ""
    if not requiere_ap and es_externa and correos_lista:
        cc_list = await obtener_correos_cc(db)
        exito, desc = await EmailService.enviar_correo(correos_input, asunto_final, html_final, correos_cc=cc_list)
        msg_correo = "Correo enviado." if exito else f"Fallo: {desc}"

    await registrar_auditoria(db, user["id"], "CREAR_APERTURA", f"Generado {consecutivo_real}")
    return {"success": True, "consecutivo": consecutivo_real, "id": comunicado_id, "message": f"Novedad {consecutivo_real} registrada. {msg_correo}"}

# ─────────────────────────────────────────────
# CIERRE DE NOVEDAD
# ─────────────────────────────────────────────

@router.post("/cierre/{comunicado_id}")
async def cerrar_novedad(comunicado_id: int, body: dict, db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    requiere_ap = body.get("requiere_aprobacion", False)
    nuevo_estado = "Pendiente Cierre" if requiere_ap else "Cerrado"

    await db.execute(text("""
        UPDATE comunicado SET estado = :est, solucion_aplicada = :sol,
            fecha_envio = :fec, html_cierre = :html, asunto_cierre = :asunto
        WHERE id = :cid
    """), {
        "est": nuevo_estado, "sol": body.get("solucion_interna", ""),
        "fec": _convert_datetime(body.get("fecha_hora_cierre", datetime.datetime.utcnow())),
        "html": body.get("html"), "asunto": body.get("asunto_norm"),
        "cid": comunicado_id
    })

    correos_str = body.get("correos_finales", "")
    correos_lista = [e.strip() for e in correos_str.split(",") if e.strip()]
    await db.execute(text("""
        INSERT INTO comunicado_destinatario (comunicado_id, tercero_id, email, estado, detalle)
        VALUES (:cid, :tid, :em, :est, :det)
    """), {
        "cid": comunicado_id, "tid": body.get("tercero_id"),
        "em": json.dumps(correos_lista),
        "est": "Pendiente" if requiere_ap else "Cierre Enviado",
        "det": body.get("solucion_interna", "")
    })
    await db.commit()

    msg_correo = ""
    if not requiere_ap and correos_lista:
        cc_list = await obtener_correos_cc(db)
        exito, desc = await EmailService.enviar_correo(correos_str, body.get("asunto_norm", ""), body.get("html", ""), correos_cc=cc_list)
        msg_correo = "Correo enviado." if exito else f"Fallo: {desc}"

    await registrar_auditoria(db, user["id"], "CERRAR_INCIDENTE", f"Cierre del incidente ID {comunicado_id}")
    return {"success": True, "message": f"Incidente actualizado. {msg_correo}"}

# ─────────────────────────────────────────────
# APROBAR / RECHAZAR
# ─────────────────────────────────────────────

@router.post("/aprobar/{comunicado_id}")
async def aprobar_comunicado(comunicado_id: int, db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    com = (await db.execute(text("SELECT * FROM comunicado WHERE id = :cid"), {"cid": comunicado_id})).mappings().first()
    if not com:
        raise HTTPException(status_code=404, detail="Comunicado no encontrado")

    if "Apertura" in com["estado"] or "Mantenimiento" in com["estado"]:
        nuevo_estado = "Abierto"
    else:
        nuevo_estado = "Cerrado"

    await db.execute(text("UPDATE comunicado SET estado = :est, aprobado_por = :uid, requiere_aprobacion = FALSE WHERE id = :cid"), {
        "est": nuevo_estado, "uid": user["id"], "cid": comunicado_id
    })

    dest = (await db.execute(text("SELECT email FROM comunicado_destinatario WHERE comunicado_id = :cid LIMIT 1"), {"cid": comunicado_id})).mappings().first()
    await db.execute(text("UPDATE comunicado_destinatario SET estado = 'Enviado' WHERE comunicado_id = :cid"), {"cid": comunicado_id})
    await db.commit()

    msg_correo = ""
    if dest and dest["email"]:
        emails = json.loads(dest["email"]) if isinstance(dest["email"], str) else dest["email"]
        if emails:
            html = com["html_cierre"] if com["html_cierre"] else com["html_final"]
            cc_list = await obtener_correos_cc(db)
            exito, desc = await EmailService.enviar_correo(",".join(emails), com["asunto_final"], html, correos_cc=cc_list)
            msg_correo = "Correo enviado." if exito else f"Fallo: {desc}"

    await registrar_auditoria(db, user["id"], "APROBAR_COMUNICADO", f"Aprob\u00f3 comunicado {com['consecutivo_num']}")
    return {"success": True, "message": f"Comunicado {com['consecutivo_num']} aprobado. {msg_correo}"}

@router.post("/rechazar/{comunicado_id}")
async def rechazar_comunicado(comunicado_id: int, db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    com = (await db.execute(text("SELECT consecutivo_num FROM comunicado WHERE id = :cid"), {"cid": comunicado_id})).mappings().first()
    if not com:
        raise HTTPException(status_code=404, detail="Comunicado no encontrado")

    await db.execute(text("UPDATE comunicado SET estado = 'Rechazado', aprobado_por = :uid, requiere_aprobacion = FALSE WHERE id = :cid"), {
        "uid": user["id"], "cid": comunicado_id
    })
    await db.commit()
    await registrar_auditoria(db, user["id"], "RECHAZAR_COMUNICADO", f"Rechazó comunicado {com['consecutivo_num']}")
    return {"success": True, "message": f"Comunicado {com['consecutivo_num']} rechazado."}

# ─────────────────────────────────────────────
# REENVÍO
# ─────────────────────────────────────────────

@router.post("/reenviar")
async def reenviar_comunicado(body: dict, db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    correos_str = body.get("correos", "")
    asunto = body.get("asunto", "")
    html = body.get("html", "")
    com_id = body.get("com_id")
    tipo = body.get("tipo_reenvio", "")
    consecutivo = body.get("consecutivo", "")

    correos_lista = [c.strip() for c in correos_str.split(",") if c.strip()]
    if not correos_lista:
        raise HTTPException(status_code=400, detail="Debe especificar al menos un correo")

    exito, msg = await EmailService.enviar_correo(correos_str, asunto, html, es_reenvio=True)
    if not exito:
        raise HTTPException(status_code=500, detail=f"Error al enviar: {msg}")

    await db.execute(text("""
        INSERT INTO comunicado_destinatario (comunicado_id, email, estado, detalle)
        VALUES (:cid, :em, 'Reenviado', :det)
    """), {"cid": com_id, "em": json.dumps(correos_lista), "det": f"Reenvío: {tipo}"})
    await db.commit()

    await registrar_auditoria(db, user["id"], "REENVIO_COMUNICADO", f"Reenvió {tipo} del caso {consecutivo}")
    return {"success": True, "message": f"Reenviado a {len(correos_lista)} correo(s)."}

# ─────────────────────────────────────────────
# EDICIÓN DE TEXTOS
# ─────────────────────────────────────────────

@router.put("/{comunicado_id}/editar")
async def editar_comunicado(comunicado_id: int, body: dict, db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    com = (await db.execute(text("SELECT consecutivo_num, descripcion, solucion_aplicada FROM comunicado WHERE id = :cid"), {"cid": comunicado_id})).mappings().first()
    if not com:
        raise HTTPException(status_code=404, detail="Comunicado no encontrado")

    new_desc = body.get("descripcion")
    new_sol = body.get("solucion")
    cambios = False

    if new_desc is not None and new_desc != com["descripcion"]:
        await db.execute(text("""INSERT INTO comunicado_historial (comunicado_id, analista_id, campo_modificado, valor_anterior, valor_nuevo)
            VALUES (:cid, :uid, 'descripcion', :oldv, :newv)"""), {"cid": comunicado_id, "uid": user["id"], "oldv": com["descripcion"], "newv": new_desc})
        cambios = True
    if new_sol is not None and new_sol != com["solucion_aplicada"]:
        await db.execute(text("""INSERT INTO comunicado_historial (comunicado_id, analista_id, campo_modificado, valor_anterior, valor_nuevo)
            VALUES (:cid, :uid, 'solucion', :oldv, :newv)"""), {"cid": comunicado_id, "uid": user["id"], "oldv": com["solucion_aplicada"], "newv": new_sol})
        cambios = True

    if cambios:
        await db.execute(text("UPDATE comunicado SET descripcion = :d, solucion_aplicada = :s WHERE id = :cid"), {
            "d": new_desc or com["descripcion"], "s": new_sol or com["solucion_aplicada"], "cid": comunicado_id
        })
        await db.commit()

    if cambios:
        await registrar_auditoria(db, user["id"], "EDICION_COMUNICADO", f"Editó textos del comunicado {com['consecutivo_num']}")

    return {"success": True, "message": "Comunicado actualizado." if cambios else "Sin cambios detectados."}

# ─────────────────────────────────────────────
# DETALLE E HISTORIAL DE CAMBIOS
# ─────────────────────────────────────────────

@router.get("/detalle/{comunicado_id}")
async def get_detalle_comunicado(comunicado_id: int, db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    result = await db.execute(text("""
        SELECT c.*, s.nombre as servicio_nom, p.nombre as plataforma_nom,
               CONCAT(a.nombre, ' ', a.apellido) as analista_nom,
               tc.nombre as tipo_comunicado_nom
        FROM comunicado c
        JOIN servicio s ON c.servicio_id = s.id
        LEFT JOIN plataforma p ON c.plataforma_id = p.id
        LEFT JOIN tipo_comunicado tc ON c.tipo_comunicado_id = tc.id
        LEFT JOIN analista a ON c.analista_id = a.id
        WHERE c.id = :cid
    """), {"cid": comunicado_id})
    com = result.mappings().first()
    if not com:
        raise HTTPException(status_code=404, detail="Comunicado no encontrado")

    dest = (await db.execute(text("SELECT email FROM comunicado_destinatario WHERE comunicado_id = :cid LIMIT 1"), {"cid": comunicado_id})).mappings().first()

    return {
        **dict(com),
        "fecha_creacion": str(com["fecha_creacion"]) if com["fecha_creacion"] else None,
        "fecha_envio": str(com["fecha_envio"]) if com["fecha_envio"] else None,
        "emails_originales": json.loads(dest["email"]) if dest and dest["email"] else []
    }

@router.get("/historial-cambios/{comunicado_id}")
async def get_historial_cambios(comunicado_id: int, db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    result = await db.execute(text("""
        SELECT ch.*, CONCAT(a.nombre, ' ', a.apellido) as analista_nom
        FROM comunicado_historial ch
        JOIN analista a ON ch.analista_id = a.id
        WHERE ch.comunicado_id = :cid
        ORDER BY ch.fecha_cambio DESC
    """), {"cid": comunicado_id})
    return [dict(r, fecha_cambio=str(r["fecha_cambio"])) for r in result.mappings().all()]

# ─────────────────────────────────────────────
# LISTADOS EXISTENTES (preservados y mejorados)
# ─────────────────────────────────────────────

@router.get("/abiertos")
async def get_comunicados_abiertos(
    tipo: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    filtro_extra = ""
    if tipo == "incidente":
        filtro_extra = "AND (tc.nombre IS NULL OR LOWER(tc.nombre) NOT LIKE '%mantenimiento%')"
    elif tipo == "mantenimiento":
        filtro_extra = "AND tc.nombre IS NOT NULL AND LOWER(tc.nombre) LIKE '%mantenimiento%'"

    where_parts, params = await _build_filtros_restriccion(db, user)
    restriccion = f" AND {' AND '.join(where_parts)}" if where_parts else ""

    query = text(f"""
        SELECT c.id, c.consecutivo_num, c.asunto_final, c.plataforma_id, p.nombre AS plataforma_nom,
               s.id AS servicio_id, s.nombre AS servicio_nom, c.fecha_creacion, c.descripcion,
               c.afectacion, c.estado, c.escalado, c.requiere_aprobacion,
               MAX(t.id) AS tercero_id, MAX(t.nombre) AS tercero_nom,
               MAX(cd.email) AS emails_apertura, tc.id AS tipo_comunicado_id, tc.nombre AS tipo_comunicado_nom
        FROM comunicado c
        JOIN servicio s ON c.servicio_id = s.id
        LEFT JOIN plataforma p ON c.plataforma_id = p.id
        LEFT JOIN tipo_comunicado tc ON c.tipo_comunicado_id = tc.id
        LEFT JOIN comunicado_destinatario cd ON cd.comunicado_id = c.id AND cd.estado = 'Enviado'
        LEFT JOIN tercero t ON cd.tercero_id = t.id
        WHERE c.estado = 'Abierto' {filtro_extra} {restriccion}
        GROUP BY c.id
        ORDER BY c.fecha_creacion DESC
    """)
    result = await db.execute(query, params)
    rows = result.mappings().all()
    return [{**dict(r), "fecha_creacion": str(r["fecha_creacion"])} for r in rows]

@router.get("/historial")
async def get_historial(
    search: Optional[str] = "",
    servicio: Optional[str] = "",
    estado: Optional[str] = "",
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    conditions = []
    params = {}
    if search:
        conditions.append("(c.asunto_final LIKE :s OR c.descripcion LIKE :s)")
        params["s"] = f"%{search}%"
    if servicio:
        conditions.append("s.nombre = :sv")
        params["sv"] = servicio
    if estado:
        conditions.append("c.estado = :est")
        params["est"] = estado

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    where_parts, params2 = await _build_filtros_restriccion(db, user)
    if where_parts:
        extra_where = " AND " + " AND ".join(where_parts)
        where_clause = (where_clause + extra_where) if conditions else ("WHERE " + " AND ".join(where_parts))
        params.update(params2)

    query = text(f"""
        SELECT c.id, c.consecutivo_num as consecutivo, s.nombre as servicio,
               c.estado, c.fecha_creacion as fecha, c.asunto_final as asunto,
               c.descripcion, c.solucion_aplicada as solucion,
               c.html_final, c.html_cierre, c.asunto_cierre, c.consecutivo_num
        FROM comunicado c
        JOIN servicio s ON c.servicio_id = s.id
        {where_clause}
        ORDER BY c.id DESC LIMIT 200
    """)
    result = await db.execute(query, params)
    rows = result.mappings().all()
    return [{**dict(r), "fecha": str(r["fecha"]) if r["fecha"] else None} for r in rows]

@router.get("/pending-approval")
async def get_pending_approval(db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    permisos = await get_permisos_usuario(db, user["rol"])
    if not permisos.get("puede_aprobar") and not permisos.get("ver_aprobaciones"):
        raise HTTPException(status_code=403, detail="No tienes permisos para ver aprobaciones pendientes")

    where_parts, params = await _build_filtros_restriccion(db, user)
    restriccion = f" AND {' AND '.join(where_parts)}" if where_parts else ""

    result = await db.execute(text(f"""
        SELECT c.*, s.nombre AS servicio_nom, a.nombre as analista_nom
        FROM comunicado c
        JOIN servicio s ON c.servicio_id = s.id
        JOIN analista a ON c.analista_id = a.id
        WHERE c.estado LIKE 'Pendiente%' {restriccion}
        ORDER BY c.fecha_creacion DESC
    """), params)
    rows = result.mappings().all()
    return [{**dict(r), "fecha_creacion": str(r["fecha_creacion"]),
             "fecha_envio": str(r["fecha_envio"]) if r.get("fecha_envio") else None} for r in rows]

@router.post("/sla-check")
async def sla_check(db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    await revisar_y_escalar_slas(db)
    return {"success": True, "message": "Verificación de SLA completada"}

@router.get("/estadisticas-sidebar")
async def get_estadisticas_sidebar(db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    servicios_rest = await get_servicios_restringidos(db, user["rol"])
    permisos = await get_permisos_usuario(db, user["rol"])
    params: dict = {}

    where_parts = []
    if servicios_rest:
        placeholders = ",".join([f":sv{i}" for i in range(len(servicios_rest))])
        where_parts.append(f"c.servicio_id IN ({placeholders})")
        for i, sid in enumerate(servicios_rest):
            params[f"sv{i}"] = sid
    if permisos.get("ver_solo_propios"):
        where_parts.append("c.analista_id = :uid")
        params["uid"] = user["id"]

    where_clause = " AND ".join(where_parts) if where_parts else "1=1"
    where_ext = f"AND {where_clause}" if where_parts else ""

    total_q = await db.execute(text(f"SELECT COUNT(*) as total FROM comunicado c WHERE {where_clause}"), params)
    total = total_q.mappings().first()["total"]
    cerrados_q = await db.execute(text(f"SELECT COUNT(*) as cerrados FROM comunicado c WHERE c.estado = 'Cerrado' {where_ext}"), params)
    cerrados = cerrados_q.mappings().first()["cerrados"]
    avg_q = await db.execute(text(f"SELECT AVG(TIMESTAMPDIFF(MINUTE, fecha_creacion, fecha_envio)) as avg_min FROM comunicado c WHERE c.estado = 'Cerrado' AND c.fecha_envio IS NOT NULL AND c.fecha_creacion IS NOT NULL {where_ext}"), params)
    avg_row = avg_q.mappings().first()
    pct_cierre = round((cerrados / total * 100) if total > 0 else 0, 1)
    tiempo_prom = round(float(avg_row["avg_min"]) if avg_row and avg_row["avg_min"] is not None else 0.0)
    return {"pct_resolucion": pct_cierre, "tiempo_promedio": tiempo_prom, "total": total, "cerrados": cerrados}

@router.get("/config-sla")
async def get_config_sla(db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    result = await db.execute(
        text("SELECT sla_horas, correo_escalacion, correo_seguridad FROM configuracion_sistema WHERE id = 1")
    )
    row = result.mappings().first()
    if not row:
        return {"sla_horas": 4, "correo_escalacion": "directores_ti@empresa.com", "correo_seguridad": "admin_seguridad@empresa.com"}
    return dict(row)

@router.post("/reglas-preview")
async def preview_regla_global(body: dict, db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    from app.services import evaluar_regla, format_seguro
    plat_id = body.get("plat_id")
    serv_id = body.get("serv_id")
    tipo_id = body.get("tipo_id")
    fase = body.get("fase", "APERTURA")
    terc_id = body.get("terc_id")
    kwargs = body.get("kwargs", {})
    regla = await evaluar_regla(db, plat_id, serv_id, tipo_id, fase, terc_id)
    entidad = format_seguro(regla["entidad_afectada"], **kwargs)
    regla["entidad_formateada"] = entidad.strip()
    return regla

@router.get("/pendientes-count")
async def get_pendientes_count(db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    result = await db.execute(text("SELECT COUNT(*) as total FROM comunicado WHERE estado LIKE 'Pendiente%'"))
    return {"pendientes": result.mappings().first()["total"]}

# Keep the abiertos filter endpoint for backwards compatibility
@router.get("/abiertos-sin-filtro")
async def get_abiertos_sin_filtro(db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    result = await db.execute(text("""
        SELECT c.id, c.consecutivo_num, c.asunto_final, c.estado, c.fecha_creacion,
               s.nombre as servicio_nom
        FROM comunicado c
        JOIN servicio s ON c.servicio_id = s.id
        WHERE c.estado = 'Abierto'
        ORDER BY c.fecha_creacion DESC
    """))
    return [dict(r, fecha_creacion=str(r["fecha_creacion"])) for r in result.mappings().all()]
