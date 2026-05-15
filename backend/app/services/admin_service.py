from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

async def get_system_config(db: AsyncSession) -> dict:
    result = await db.execute(
        text("SELECT sla_horas, correo_escalacion, correo_seguridad FROM configuracion_sistema WHERE id = 1")
    )
    row = result.mappings().first()
    if row:
        return dict(row)
    return {'sla_horas': 4, 'correo_escalacion': 'directores_ti@empresa.com', 'correo_seguridad': 'admin_seguridad@empresa.com'}
