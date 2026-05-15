export interface Catalogo {
  id: number;
  nombre: string;
}

export interface Analista extends Catalogo {
  apellido: string;
  correo: string;
  rol: string;
  estado: boolean;
}

export interface Plataforma extends Catalogo {
  estado: boolean;
}

export interface Servicio extends Catalogo {
  estado: boolean;
}

export interface TipoComunicado extends Catalogo {
  serie_id: number;
}

export interface Plantilla {
  id: number;
  plataforma_id: number | null;
  tipo_comunicado_id: number;
  version?: number;
  asunto: string;
  html: string;
  estado?: boolean;
}

export interface Tercero extends Catalogo {
  estado: boolean;
}

export interface Comunicado {
  id: number;
  consecutivo_num: string;
  asunto_final: string;
  html_final: string;
  descripcion: string;
  afectacion: string;
  solucion_aplicada?: string;
  analista_id: number;
  servicio_id: number;
  plataforma_id?: number;
  tipo_comunicado_id?: number;
  estado: string;
  fecha_creacion: string;
  fecha_envio?: string;
  escalado: boolean;
  requiere_aprobacion: boolean;
  aprobado_por?: number;
  html_cierre?: string;
  asunto_cierre?: string;
  servicio_nom?: string;
  plataforma_nom?: string;
  analista_nom?: string;
  tipo_comunicado_nom?: string;
  emails_originales?: string[];
}

export interface ReglaTexto {
  id: number;
  plataforma_id?: number;
  servicio_id?: number;
  tercero_id?: number;
  tipo_comunicado_id?: number;
  fase: string;
  entidad_afectada: string;
  asunto_template: string;
  descripcion_template: string;
  estado: boolean;
  plat_nom?: string;
  serv_nom?: string;
  tipo_nom?: string;
  terc_nom?: string;
}

export interface ReglaResult {
  entidad_afectada: string;
  asunto_template: string;
  descripcion_template: string;
  entidad_formateada?: string;
}

export interface RolPermisos {
  ver_aprobaciones: boolean;
  ver_apertura: boolean;
  ver_cierre: boolean;
  ver_mantenimiento: boolean;
  ver_edicion: boolean;
  ver_reportes: boolean;
  ver_admin: boolean;
  puede_aprobar: boolean;
  ver_solo_propios: boolean;
  exige_aprobacion: boolean;
}

export interface ConfigSistema {
  sla_horas: number;
  correo_escalacion: string;
  correo_seguridad: string;
}

export interface Usuario {
  id: number;
  nombre: string;
  apellido: string;
  correo: string;
  rol: string;
  estado: boolean;
}

export interface Vinculo {
  id: number;
  servicio_id: number;
  tercero_id: number;
  servicio_nom: string;
  tercero_nom: string;
}

export interface CorreoInterno {
  id: number;
  email: string;
  estado: boolean;
}

export interface ServicioCorreo {
  id: number;
  servicio_id: number;
  email: string;
  nombre?: string;
  estado: boolean;
  plataforma_id?: number;
  tercero_id?: number;
  plataforma_nom?: string;
  tercero_nom?: string;
}

export interface AuditLog {
  fecha: string;
  analista: string;
  accion: string;
  detalles: string;
}

export interface KPIData {
  total_eventos: number;
  activos: number;
  cerrados: number;
  escalados: number;
  sla_pct: number;
  pct_cierre: number;
  mttr_min: number;
}

export interface DashboardData {
  kpi: KPIData;
  activos: any[];
  top_servicios: any[];
  tendencia: any[];
  plataformas: any[];
}
