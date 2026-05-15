from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import date, datetime
from typing import Optional
from app.core.database import get_db
from app.api.deps import get_current_user, get_permisos_usuario, get_servicios_restringidos
import json

router = APIRouter(prefix="/reportes", tags=["reportes"])

@router.get("/dashboard")
async def get_dashboard_data(
    fecha_inicio: Optional[str] = None,
    fecha_fin: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    where_extra = ""
    params = {}
    if fecha_inicio and fecha_fin:
        where_extra = "WHERE c.fecha_creacion >= :fi AND c.fecha_creacion <= :ff"
        params["fi"] = fecha_inicio
        params["ff"] = f"{fecha_fin} 23:59:59"

    servicios_rest = await get_servicios_restringidos(db, user["rol"])
    permisos_u = await get_permisos_usuario(db, user["rol"])
    filtros_adic = []
    if servicios_rest:
        ph = ",".join([f":srv{i}" for i in range(len(servicios_rest))])
        filtros_adic.append(f"c.servicio_id IN ({ph})")
        for i, sid in enumerate(servicios_rest):
            params[f"srv{i}"] = sid
    if permisos_u.get("ver_solo_propios"):
        filtros_adic.append("c.analista_id = :uid")
        params["uid"] = user["id"]

    restriccion = " AND " + " AND ".join(filtros_adic) if filtros_adic else ""
    base_where = where_extra
    if restriccion:
        base_where = (where_extra + restriccion) if where_extra else ("WHERE " + restriccion[5:])

    # KPI principales
    total = await db.execute(text(f"SELECT COUNT(*) as total FROM comunicado c {base_where}"), params)
    total_val = total.mappings().first()['total']

    cerrados = await db.execute(text(f"SELECT COUNT(*) as total FROM comunicado c WHERE c.estado = 'Cerrado' {restriccion}"), params)
    cerrados_val = cerrados.mappings().first()['total']

    escalados = await db.execute(text(f"SELECT COUNT(*) as total FROM comunicado c WHERE c.escalado = TRUE {restriccion}"), params)
    escalados_val = escalados.mappings().first()['total']

    mttr_q = await db.execute(text(f"""
        SELECT AVG(TIMESTAMPDIFF(MINUTE, fecha_creacion, fecha_envio)) as mttr
        FROM comunicado c WHERE c.estado = 'Cerrado' AND c.fecha_envio IS NOT NULL {restriccion}
    """), params)
    mttr_val = mttr_q.mappings().first()['mttr'] or 0

    # Incidentes activos
    activos_where = f"WHERE c.estado = 'Abierto' {restriccion}" if restriccion else "WHERE c.estado = 'Abierto'"
    activos_q = await db.execute(text(f"""
        SELECT c.id, c.consecutivo_num, c.asunto_final, c.descripcion, c.estado, c.afectacion,
               c.fecha_creacion, s.nombre as servicio, c.escalado
        FROM comunicado c JOIN servicio s ON c.servicio_id = s.id
        {activos_where}
        ORDER BY c.fecha_creacion DESC
    """), params)
    activos = [dict(r, fecha_creacion=str(r['fecha_creacion'])) for r in activos_q.mappings().all()]

    # Incidentes por servicio (top)
    top_svc = await db.execute(text(f"""
        SELECT s.nombre, COUNT(*) as cantidad
        FROM comunicado c JOIN servicio s ON c.servicio_id = s.id
        {base_where} GROUP BY s.nombre ORDER BY cantidad DESC LIMIT 10
    """), params)
    top_servicios = [dict(r) for r in top_svc.mappings().all()]

    # Incidentes por dia (ultimos 30)
    last_30_q = f"SELECT DATE(fecha_creacion) as dia, COUNT(*) as cantidad FROM comunicado"
    if restriccion:
        last_30_q += f" WHERE fecha_creacion >= DATE_SUB(CURDATE(), INTERVAL 30 DAY) {restriccion}"
    else:
        last_30_q += " WHERE fecha_creacion >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)"
    last_30_q += " GROUP BY DATE(fecha_creacion) ORDER BY dia"
    last_30 = await db.execute(text(last_30_q), params)
    tendencia = [dict(r, dia=str(r['dia'])) for r in last_30.mappings().all()]

    # Por plataforma
    plat_q = await db.execute(text(f"""
        SELECT p.nombre, COUNT(*) as cantidad
        FROM comunicado c JOIN plataforma p ON c.plataforma_id = p.id
        {base_where} GROUP BY p.nombre
    """), params)
    plataformas = [dict(r) for r in plat_q.mappings().all()]

    # SLA por hora MTTR
    sla_pct = ((total_val - escalados_val) / total_val * 100) if total_val > 0 else 100
    pct_cierre = (cerrados_val / total_val * 100) if total_val > 0 else 0

    return {
        "kpi": {
            "total_eventos": total_val,
            "activos": len(activos),
            "cerrados": cerrados_val,
            "escalados": escalados_val,
            "sla_pct": round(sla_pct, 1),
            "pct_cierre": round(pct_cierre, 1),
            "mttr_min": round(float(mttr_val), 1)
        },
        "activos": activos,
        "top_servicios": top_servicios,
        "tendencia": tendencia,
        "plataformas": plataformas
    }

@router.get("/export")
async def export_report(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    result = await db.execute(text("""
        SELECT c.consecutivo_num, s.nombre as servicio, p.nombre as plataforma,
               tc.nombre as tipo, c.estado, c.afectacion, c.fecha_creacion, c.fecha_envio,
               c.escalado, c.descripcion, c.solucion_aplicada,
               CONCAT(a.nombre, ' ', a.apellido) as analista
        FROM comunicado c
        JOIN servicio s ON c.servicio_id = s.id
        LEFT JOIN plataforma p ON c.plataforma_id = p.id
        LEFT JOIN tipo_comunicado tc ON c.tipo_comunicado_id = tc.id
        LEFT JOIN analista a ON c.analista_id = a.id
        ORDER BY c.id DESC
    """))
    rows = [dict(r, fecha_creacion=str(r['fecha_creacion']),
                 fecha_envio=str(r['fecha_envio']) if r['fecha_envio'] else None)
            for r in result.mappings().all()]
    return {"data": rows, "total": len(rows)}
