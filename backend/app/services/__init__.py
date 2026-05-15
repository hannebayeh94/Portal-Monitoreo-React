from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Optional, List
import string
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class SafeDict(dict):
    def __missing__(self, key):
        return '{' + key + '}'

def format_seguro(template_str: str, **kwargs) -> str:
    if not template_str:
        return ""
    formatter = string.Formatter()
    return formatter.vformat(template_str, (), SafeDict(**kwargs))

async def evaluar_regla(db: AsyncSession, plat_id: Optional[int], serv_id: Optional[int],
                         tipo_id: Optional[int], fase: str, terc_id: Optional[int] = None) -> dict:
    query = text("""
        SELECT * FROM regla_texto
        WHERE fase = :fase AND estado = 1
        AND (plataforma_id = :plat_id OR plataforma_id IS NULL)
        AND (servicio_id = :serv_id OR servicio_id IS NULL)
        AND (tipo_comunicado_id = :tipo_id OR tipo_comunicado_id IS NULL)
        AND (tercero_id = :terc_id OR tercero_id IS NULL)
        ORDER BY
            (plataforma_id IS NOT NULL) DESC,
            (servicio_id IS NOT NULL) DESC,
            (tercero_id IS NOT NULL) DESC,
            (tipo_comunicado_id IS NOT NULL) DESC
        LIMIT 1
    """)
    result = await db.execute(query, {"fase": fase, "plat_id": plat_id, "serv_id": serv_id,
                                        "tipo_id": tipo_id, "terc_id": terc_id})
    regla = result.mappings().first()
    if not regla:
        return {
            'entidad_afectada': 'la entidad {tercero}',
            'asunto_template': '{consecutivo} - Comunicado sobre {servicio}',
            'descripcion_template': 'Notificaci\u00f3n del servicio {servicio} para {entidad}.'
        }
    return dict(regla)

def calcular_tiempo_transcurrido(inicio: datetime, fin: datetime) -> str:
    diff = fin - inicio
    total_segundos = int(diff.total_seconds())
    if total_segundos < 0:
        return "Error en fechas"
    if total_segundos < 60:
        return "Menos de 1 minuto"
    horas, minutos = total_segundos // 3600, (total_segundos % 3600) // 60
    texto = []
    if horas > 0:
        texto.append(f"{horas} hora{'s' if horas != 1 else ''}")
    if minutos > 0:
        texto.append(f"{minutos} minuto{'s' if minutos != 1 else ''}")
    return ", ".join(texto)

def formatear_fecha_es(fecha, hora=None):
    meses = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
    if isinstance(fecha, str):
        try:
            dt_obj = datetime.fromisoformat(str(fecha).replace('Z', '+00:00').split('+')[0])
            return f"{dt_obj.day:02d} {meses[dt_obj.month - 1]} {dt_obj.year} - {dt_obj.strftime('%I:%M %p')} (COT)"
        except:
            return str(fecha)
    fecha_str = f"{fecha.day:02d} {meses[fecha.month - 1]} {fecha.year}"
    if hora:
        return f"{fecha_str} - {hora.strftime('%I:%M %p')} (COT)"
    return fecha_str

def calcular_estado_sla(fecha_creacion: datetime, sla_horas: int) -> str:
    if not isinstance(fecha_creacion, datetime):
        return "N/A"
    horas_pasadas = (datetime.now() - fecha_creacion).total_seconds() / 3600
    if horas_pasadas >= sla_horas:
        return "Incumplido"
    if horas_pasadas >= (sla_horas * 0.75):
        return "En Riesgo"
    return "A tiempo"

async def obtener_correos_cc(db: AsyncSession) -> List[str]:
    result = await db.execute(text("SELECT email FROM correo_interno_cc WHERE estado = TRUE"))
    return [r["email"].strip() for r in result.mappings().all()]
