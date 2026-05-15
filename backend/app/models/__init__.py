from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, TIMESTAMP, text
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class Analista(Base):
    __tablename__ = "analista"
    id = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(50), nullable=False)
    apellido = Column(String(50), nullable=False)
    correo = Column(String(100), nullable=False)
    estado = Column(Boolean, default=True)
    password = Column(String(255), nullable=False)
    rol = Column(String(50), nullable=False, default="Monitoreo")

class Comunicado(Base):
    __tablename__ = "comunicado"
    id = Column(Integer, primary_key=True, autoincrement=True)
    plataforma_id = Column(Integer, ForeignKey("plataforma.id"))
    tipo_comunicado_id = Column(Integer, ForeignKey("tipo_comunicado.id"))
    serie_id = Column(Integer, ForeignKey("serie.id"))
    consecutivo_num = Column(String(20))
    asunto_final = Column(String(200))
    html_final = Column(Text)
    descripcion = Column(Text)
    afectacion = Column(String(255))
    solucion_aplicada = Column(Text)
    analista_id = Column(Integer, ForeignKey("analista.id"))
    servicio_id = Column(Integer, ForeignKey("servicio.id"))
    estado = Column(String(50))
    fecha_creacion = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    fecha_envio = Column(DateTime, nullable=True)
    escalado = Column(Boolean, default=False)
    requiere_aprobacion = Column(Boolean, default=False)
    aprobado_por = Column(Integer, ForeignKey("analista.id"))
    html_cierre = Column(Text, nullable=True)
    asunto_cierre = Column(String(200), nullable=True)

class ComunicadoDestinatario(Base):
    __tablename__ = "comunicado_destinatario"
    id = Column(Integer, primary_key=True, autoincrement=True)
    comunicado_id = Column(Integer, ForeignKey("comunicado.id"))
    tercero_id = Column(Integer, ForeignKey("tercero.id"))
    email = Column(Text)
    estado = Column(String(20))
    detalle = Column(Text)
    fecha_creacion = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))

class ComunicadoHistorial(Base):
    __tablename__ = "comunicado_historial"
    id = Column(Integer, primary_key=True, autoincrement=True)
    comunicado_id = Column(Integer, ForeignKey("comunicado.id"), nullable=False)
    analista_id = Column(Integer, ForeignKey("analista.id"), nullable=False)
    campo_modificado = Column(String(50), nullable=False)
    valor_anterior = Column(Text)
    valor_nuevo = Column(Text)
    fecha_cambio = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))

class Plataforma(Base):
    __tablename__ = "plataforma"
    id = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(50), nullable=False)
    estado = Column(Boolean, default=True)
    fecha_actualizacion = Column(DateTime, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"))

class Servicio(Base):
    __tablename__ = "servicio"
    id = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(100), nullable=False)
    estado = Column(Boolean, default=True)
    fecha_creacion = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))

class TipoComunicado(Base):
    __tablename__ = "tipo_comunicado"
    id = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(50), nullable=False)
    serie_id = Column(Integer, ForeignKey("serie.id"))
    estado = Column(Boolean, default=True)

class Serie(Base):
    __tablename__ = "serie"
    id = Column(Integer, primary_key=True, autoincrement=True)
    codigo = Column(String(10), nullable=False)
    estado = Column(Boolean, default=True)

class ConsecutivoSerie(Base):
    __tablename__ = "consecutivo_serie"
    serie_id = Column(Integer, ForeignKey("serie.id"), primary_key=True)
    siguiente_valor = Column(Integer, nullable=False)

class Tercero(Base):
    __tablename__ = "tercero"
    id = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(100), nullable=False)
    estado = Column(Boolean, default=True)

class Plantilla(Base):
    __tablename__ = "plantilla"
    id = Column(Integer, primary_key=True, autoincrement=True)
    plataforma_id = Column(Integer, ForeignKey("plataforma.id"))
    tipo_comunicado_id = Column(Integer, ForeignKey("tipo_comunicado.id"))
    version = Column(Integer, nullable=False)
    asunto = Column(String(200))
    html = Column(Text)
    estado = Column(Boolean, default=True)

class ReglaTexto(Base):
    __tablename__ = "regla_texto"
    id = Column(Integer, primary_key=True, autoincrement=True)
    plataforma_id = Column(Integer, ForeignKey("plataforma.id"))
    servicio_id = Column(Integer, ForeignKey("servicio.id"))
    tercero_id = Column(Integer, ForeignKey("tercero.id"))
    tipo_comunicado_id = Column(Integer, ForeignKey("tipo_comunicado.id"))
    fase = Column(String(50), nullable=False)
    entidad_afectada = Column(String(255))
    asunto_template = Column(String(255), nullable=False)
    descripcion_template = Column(Text, nullable=False)
    estado = Column(Boolean, default=True)

class ConfiguracionSistema(Base):
    __tablename__ = "configuracion_sistema"
    id = Column(Integer, primary_key=True)
    sla_horas = Column(Integer, nullable=False)
    correo_escalacion = Column(String(255), nullable=False)
    correo_seguridad = Column(String(255), nullable=False)

class AuditLog(Base):
    __tablename__ = "audit_log"
    id = Column(Integer, primary_key=True, autoincrement=True)
    analista_id = Column(Integer, ForeignKey("analista.id"))
    accion = Column(String(100), nullable=False)
    detalles = Column(Text)
    fecha = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))

class RolPermisos(Base):
    __tablename__ = "rol_permisos"
    rol_nombre = Column(String(50), primary_key=True)
    ver_aprobaciones = Column(Boolean, default=False)
    ver_apertura = Column(Boolean, default=True)
    ver_cierre = Column(Boolean, default=True)
    ver_mantenimiento = Column(Boolean, default=True)
    ver_edicion = Column(Boolean, default=True)
    ver_reportes = Column(Boolean, default=True)
    ver_admin = Column(Boolean, default=False)
    puede_aprobar = Column(Boolean, default=False)
    ver_solo_propios = Column(Boolean, default=False)
    exige_aprobacion = Column(Boolean, default=False)

class RolServicios(Base):
    __tablename__ = "rol_servicios"
    id = Column(Integer, primary_key=True, autoincrement=True)
    rol_nombre = Column(String(50))
    servicio_id = Column(Integer, ForeignKey("servicio.id"))

class ServicioCorreo(Base):
    __tablename__ = "servicio_correo"
    id = Column(Integer, primary_key=True, autoincrement=True)
    servicio_id = Column(Integer, ForeignKey("servicio.id"), nullable=False)
    email = Column(String(255), nullable=False)
    estado = Column(Boolean, default=True)
    plataforma_id = Column(Integer, ForeignKey("plataforma.id"))
    nombre = Column(String(100))
    tercero_id = Column(Integer, ForeignKey("tercero.id"))

class ServicioTercero(Base):
    __tablename__ = "servicio_tercero"
    id = Column(Integer, primary_key=True, autoincrement=True)
    servicio_id = Column(Integer, ForeignKey("servicio.id"))
    tercero_id = Column(Integer, ForeignKey("tercero.id"))

class CorreoInternoCC(Base):
    __tablename__ = "correo_interno_cc"
    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), nullable=False)
    estado = Column(Boolean, default=True)
