from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import datetime
from app.services.email_service import EmailService
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

async def registrar_auditoria(db: AsyncSession, analista_id, accion: str, detalles: str):
    await db.execute(
        text("INSERT INTO audit_log (analista_id, accion, detalles) VALUES (:aid, :acc, :det)"),
        {"aid": analista_id, "acc": accion, "det": detalles}
    )
    await db.commit()
    if accion in ('ADMIN_CRITICO', 'SEGURIDAD', 'ADMIN_REGLAS'):
        try:
            cfg = await db.execute(
                text("SELECT correo_seguridad FROM configuracion_sistema WHERE id = 1")
            )
            row = cfg.mappings().first()
            if row and row["correo_seguridad"]:
                html_alerta = (
                    f"<h3>Alerta de Seguridad - Portal TI</h3>"
                    f"<p><b>Acción:</b> {detalles}</p>"
                    f"<p><b>Usuario ID:</b> {analista_id}</p>"
                    f"<p><b>Fecha:</b> {datetime.now()}</p>"
                )
                await EmailService.enviar_correo(
                    row["correo_seguridad"],
                    "Alerta Crítica - Modificación en Portal TI",
                    html_alerta,
                    is_intern=True
                )
        except Exception as e:
            logger.error(f"Error enviando alerta de seguridad: {e}")

async def revisar_y_escalar_slas(db: AsyncSession):
    config = await db.execute(
        text("SELECT sla_horas, correo_escalacion, correo_seguridad FROM configuracion_sistema WHERE id = 1")
    )
    cfg = config.mappings().first()
    if not cfg:
        return
    sla_horas = cfg['sla_horas']

    result = await db.execute(text("""
        SELECT id, consecutivo_num, asunto_final, fecha_creacion, servicio_id
        FROM comunicado
        WHERE estado = 'Abierto' AND escalado = FALSE
        AND TIMESTAMPDIFF(HOUR, fecha_creacion, NOW()) >= :sla
    """), {"sla": sla_horas})
    incidentes = result.mappings().all()

    for inc in incidentes:
        try:
            asunto_esc = f"ESCALACIÓN SLA: Incidente {inc['consecutivo_num']} supera {sla_horas} horas"
            html_esc = f"""
            <h3>Aviso Automático de Escalación</h3>
            <p>El incidente <b>{inc['consecutivo_num']}</b> ({inc.get('asunto_final', '')}) ha superado el tiempo máximo de resolución de {sla_horas} horas.</p>
            <p><b>Fecha de Apertura:</b> {inc['fecha_creacion']}</p>
            <p>Por favor, revisar el estado de este caso inmediatamente.</p>
            """
            exito, _ = await EmailService.enviar_correo(cfg['correo_escalacion'], asunto_esc, html_esc, is_intern=True)
            if exito:
                async with db.begin():
                    await db.execute(text("UPDATE comunicado SET escalado = TRUE WHERE id = :id"), {"id": inc['id']})
                    await db.execute(
                        text("INSERT INTO audit_log (analista_id, accion, detalles) VALUES (:aid, :acc, :det)"),
                        {"aid": None, "acc": "SISTEMA_SLA", "det": f"Incidente {inc['consecutivo_num']} escalado automáticamente."}
                    )
        except Exception as e:
            logger.error(f"Error escalando incidente {inc.get('consecutivo_num', inc['id'])}: {e}")
