from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional, List
from datetime import datetime

# Auth
class LoginRequest(BaseModel):
    correo: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserInfo"

class UserInfo(BaseModel):
    id: int
    nombre: str
    apellido: str
    correo: str
    rol: str
    estado: bool = True

class UserInfoConPermisos(UserInfo):
    permisos: dict = {}

# Comunicado
class ComunicadoBase(BaseModel):
    plataforma_id: Optional[int] = None
    tipo_comunicado_id: Optional[int] = None
    serie_id: Optional[int] = None
    asunto_final: Optional[str] = None
    descripcion: Optional[str] = None
    afectacion: Optional[str] = None
    analista_id: Optional[int] = None
    servicio_id: Optional[int] = None
    requiere_aprobacion: bool = False
    tercero_id: Optional[int] = None
    correos_input: Optional[str] = None
    diagnostico_falla: Optional[str] = None

class ComunicadoCreate(ComunicadoBase):
    pass

class ComunicadoResponse(BaseModel):
    id: int
    consecutivo_num: Optional[str] = None
    asunto_final: Optional[str] = None
    estado: Optional[str] = None
    servicio_nom: Optional[str] = None
    plataforma_nom: Optional[str] = None
    tercero_nom: Optional[str] = None
    fecha_creacion: Optional[datetime] = None
    descripcion: Optional[str] = None
    afectacion: Optional[str] = None
    escalado: bool = False

    model_config = {"from_attributes": True}

# Reglas
class ReglaTextoCreate(BaseModel):
    plataforma_id: Optional[int] = None
    servicio_id: Optional[int] = None
    tercero_id: Optional[int] = None
    tipo_comunicado_id: Optional[int] = None
    fase: str
    entidad_afectada: str = "la entidad {tercero}"
    asunto_template: str
    descripcion_template: str

class ReglaTextoUpdate(ReglaTextoCreate):
    pass

# Admin
class ConfigSistemaUpdate(BaseModel):
    sla_horas: int
    correo_escalacion: str
    correo_seguridad: str

class ServicioCreate(BaseModel):
    nombre: str

class TerceroCreate(BaseModel):
    nombre: str

class PlantillaCreate(BaseModel):
    plataforma_id: Optional[int] = None
    tipo_comunicado_id: int
    asunto: str
    html: str

class UsuarioCreate(BaseModel):
    nombre: str
    apellido: str
    correo: str
    password: str
    rol: str = "Monitoreo"

class UsuarioUpdate(BaseModel):
    nombre: Optional[str] = None
    apellido: Optional[str] = None
    correo: Optional[str] = None
    password: Optional[str] = None
    rol: Optional[str] = None
    estado: Optional[bool] = None

class CorreoInternoCreate(BaseModel):
    emails: str  # comma separated

class ServicioCorreoCreate(BaseModel):
    servicio_id: int
    email: str
    nombre: Optional[str] = None
    plataforma_id: Optional[int] = None
    tercero_id: Optional[int] = None

class PermisosUpdate(BaseModel):
    ver_aprobaciones: bool = False
    ver_apertura: bool = True
    ver_cierre: bool = True
    ver_mantenimiento: bool = True
    ver_edicion: bool = True
    ver_reportes: bool = True
    ver_admin: bool = False
    puede_aprobar: bool = False
    ver_solo_propios: bool = False
    exige_aprobacion: bool = False
    servicios_restringidos: List[int] = []

# Generic
class MessageResponse(BaseModel):
    message: str
    success: bool = True

class PaginatedResponse(BaseModel):
    data: List[dict]
    total: int
    page: int = 1
    page_size: int = 50
