"use client";

import { useState, useEffect, useCallback } from "react";
import { AppShell } from "@/components/layout/app-shell";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { PageLoader } from "@/components/ui/spinner";
import { DataTable } from "@/components/shared/data-table";
import api from "@/lib/api-client";
import { toast } from "sonner";
import {
  Settings, SlidersHorizontal, FileText, Users, UserCog,
  Building2, Link2, Mail, Fingerprint, ScrollText,
  ChevronRight, Plus, Trash2, Save, Eye, Loader2, Edit3,
  Search, XCircle, CheckCircle2, ToggleLeft, ToggleRight
} from "lucide-react";

const adminSections = [
  { id: "sla", label: "Config. Global (SLA)", icon: SlidersHorizontal },
  { id: "reglas", label: "Reglas de Texto", icon: FileText },
  { id: "roles", label: "Roles y Permisos", icon: UserCog },
  { id: "servicios", label: "Servicios", icon: Building2 },
  { id: "terceros", label: "Terceros", icon: Users },
  { id: "vinculos", label: "Vincular Serv-Terc", icon: Link2 },
  { id: "correos", label: "Correos Servicios", icon: Mail },
  { id: "correos-int", label: "Correos Internos", icon: Mail },
  { id: "usuarios", label: "Usuarios", icon: Fingerprint },
  { id: "plantillas", label: "Plantillas HTML", icon: ScrollText },
  { id: "auditoria", label: "Auditoría", icon: ScrollText },
];

function confirmAction(msg: string): Promise<boolean> {
  return Promise.resolve(window.confirm(msg));
}

export default function AdminPage() {
  const [activeSection, setActiveSection] = useState("sla");
  const SectionIcon = adminSections.find(s => s.id === activeSection)?.icon || Settings;

  return (
    <AppShell>
      <div className="animate-fade-in">
        <div className="flex items-center gap-3 mb-6">
          <div className="p-2.5 rounded-xl bg-primary-light"><Settings className="text-primary" size={24} /></div>
          <div><h1 className="text-2xl font-extrabold text-accent">Panel de Administración</h1>
          <p className="text-sm text-muted-foreground">Configuración del sistema y auditoría</p></div>
        </div>

        <div className="flex gap-6">
          <div className="w-64 shrink-0 space-y-1">
            {adminSections.map((sec) => {
              const Icon = sec.icon;
              const isActive = activeSection === sec.id;
              return (
                <button key={sec.id} onClick={() => setActiveSection(sec.id)}
                  className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all text-left ${isActive ? "bg-primary text-white shadow-md" : "text-muted-foreground hover:text-accent hover:bg-muted"}`}>
                  <Icon size={18} />
                  <span>{sec.label}</span>
                  {isActive && <ChevronRight size={16} className="ml-auto" />}
                </button>
              );
            })}
          </div>

          <div className="flex-1">
            <Card>
              <CardContent className="p-6">
                <div className="flex items-center gap-3 mb-6">
                  <SectionIcon size={22} className="text-primary" />
                  <h2 className="text-lg font-bold text-accent">{adminSections.find(s => s.id === activeSection)?.label}</h2>
                </div>

                {activeSection === "sla" && <SLAConfig />}
                {activeSection === "reglas" && <ReglasMotor />}
                {activeSection === "roles" && <RolesPermisos />}
                {activeSection === "servicios" && <ServiciosAdmin />}
                {activeSection === "terceros" && <TercerosAdmin />}
                {activeSection === "vinculos" && <VinculosAdmin />}
                {activeSection === "correos" && <CorreosServicio />}
                {activeSection === "correos-int" && <CorreosInternos />}
                {activeSection === "usuarios" && <UsuariosAdmin />}
                {activeSection === "plantillas" && <PlantillasAdmin />}
                {activeSection === "auditoria" && <AuditoriaAdmin />}
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </AppShell>
  );
}

function SLAConfig() {
  const [cfg, setCfg] = useState({ sla_horas: 4, correo_escalacion: "", correo_seguridad: "" });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.get<any>("/admin/config").then(setCfg).catch(console.error).finally(() => setLoading(false));
  }, []);

  const guardar = async () => {
    setSaving(true);
    try {
      await api.put("/admin/config", cfg);
      toast.success("Configuración SLA actualizada");
    } catch (e: any) {
      toast.error(e.message || "Error al guardar");
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="py-8 text-center text-muted-foreground">Cargando configuración...</div>;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="space-y-2"><label className="text-sm font-semibold">Horas Límite SLA</label>
          <Input type="number" value={cfg.sla_horas} onChange={e => setCfg(f => ({ ...f, sla_horas: Number(e.target.value) }))} min={1} max={72} /></div>
        <div className="space-y-2"><label className="text-sm font-semibold">Correo Escalación</label>
          <Input value={cfg.correo_escalacion} onChange={e => setCfg(f => ({ ...f, correo_escalacion: e.target.value }))} placeholder="directores_ti@empresa.com" /></div>
        <div className="space-y-2"><label className="text-sm font-semibold">Correo Seguridad</label>
          <Input value={cfg.correo_seguridad} onChange={e => setCfg(f => ({ ...f, correo_seguridad: e.target.value }))} placeholder="admin_seguridad@empresa.com" /></div>
      </div>
      <Button onClick={guardar} disabled={saving} className="gap-2">
        {saving ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />} Actualizar Configuración</Button>
    </div>
  );
}

function ReglasMotor() {
  const [reglas, setReglas] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [reglaForm, setReglaForm] = useState({ fase: "APERTURA", plataforma_id: "", servicio_id: "", tipo_comunicado_id: "", tercero_id: "", entidad_afectada: "{tercero}", asunto_template: "{consecutivo} - Comunicado sobre {servicio}", descripcion_template: "Notificación del servicio {servicio} para {entidad}." });
  const [catalogos, setCatalogos] = useState<any>(null);
  const [preview, setPreview] = useState<any>(null);
  const [busqueda, setBusqueda] = useState("");

  const loadReglas = () => api.get<any[]>("/admin/reglas").then(setReglas);
  useEffect(() => {
    Promise.all([loadReglas(), api.get<any>("/comunicados/catalogos")])
      .then(([r, c]) => { setCatalogos(c); })
      .catch(console.error).finally(() => setLoading(false));
  }, []);

  const cargarRegla = (r: any) => {
    setEditingId(r.id);
    setReglaForm({
      fase: r.fase, plataforma_id: String(r.plataforma_id || ""),
      servicio_id: String(r.servicio_id || ""), tipo_comunicado_id: String(r.tipo_comunicado_id || ""),
      tercero_id: String(r.tercero_id || ""), entidad_afectada: r.entidad_afectada || "{tercero}",
      asunto_template: r.asunto_template, descripcion_template: r.descripcion_template
    });
    setPreview(null);
  };

  const guardarRegla = async () => {
    try {
      const body = {
        ...reglaForm,
        plataforma_id: reglaForm.plataforma_id ? Number(reglaForm.plataforma_id) : null,
        servicio_id: reglaForm.servicio_id ? Number(reglaForm.servicio_id) : null,
        tipo_comunicado_id: reglaForm.tipo_comunicado_id ? Number(reglaForm.tipo_comunicado_id) : null,
        tercero_id: reglaForm.tercero_id ? Number(reglaForm.tercero_id) : null,
      };
      if (editingId) {
        await api.put(`/admin/reglas/${editingId}`, body);
        toast.success("Regla actualizada");
      } else {
        await api.post("/admin/reglas", body);
        toast.success("Regla creada");
      }
      setEditingId(null);
      setReglaForm({ fase: "APERTURA", plataforma_id: "", servicio_id: "", tipo_comunicado_id: "", tercero_id: "", entidad_afectada: "{tercero}", asunto_template: "{consecutivo} - Comunicado sobre {servicio}", descripcion_template: "Notificación del servicio {servicio} para {entidad}." });
      await loadReglas();
    } catch (e: any) {
      toast.error(e.message || "Error al guardar regla");
    }
  };

  const eliminarRegla = async (id: number) => {
    if (!(await confirmAction("¿Eliminar esta regla permanentemente?"))) return;
    try {
      await api.delete(`/admin/reglas/${id}`);
      toast.success("Regla eliminada");
      setReglas(reglas.filter(r => r.id !== id));
    } catch (e: any) {
      toast.error(e.message || "Error al eliminar");
    }
  };

  const previsualizar = async () => {
    try {
      const pId = reglaForm.plataforma_id ? Number(reglaForm.plataforma_id) : null;
      const sId = reglaForm.servicio_id ? Number(reglaForm.servicio_id) : null;
      const tId = reglaForm.tipo_comunicado_id ? Number(reglaForm.tipo_comunicado_id) : null;
      const tercId = reglaForm.tercero_id ? Number(reglaForm.tercero_id) : null;
      const kwargs = { consecutivo: "PREV-000", plataforma: "Test Plataforma", servicio: "Test Servicio", tercero: "Aliado" };
      const result = await api.post<any>("/comunicados/reglas-preview", {
        plat_id: pId, serv_id: sId, tipo_id: tId, fase: reglaForm.fase, terc_id: tercId, kwargs
      });
      setPreview(result);
    } catch (e: any) {
      toast.error(e.message || "Error en preview");
    }
  };

  const reglasFiltradas = reglas.filter(r =>
    !busqueda || r.fase?.toLowerCase().includes(busqueda.toLowerCase()) ||
    r.asunto_template?.toLowerCase().includes(busqueda.toLowerCase()) ||
    r.plat_nom?.toLowerCase().includes(busqueda.toLowerCase()) ||
    r.serv_nom?.toLowerCase().includes(busqueda.toLowerCase())
  );

  if (loading) return <div className="py-8 text-center text-muted-foreground">Cargando reglas...</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2 mb-2">
        {editingId && <Badge variant="info">Editando Regla #{editingId}</Badge>}
        {!editingId && <Badge variant="success">Nueva Regla</Badge>}
        <button className="text-xs text-primary hover:underline ml-auto" onClick={() => { setEditingId(null); setReglaForm({ fase: "APERTURA", plataforma_id: "", servicio_id: "", tipo_comunicado_id: "", tercero_id: "", entidad_afectada: "{tercero}", asunto_template: "{consecutivo} - Comunicado sobre {servicio}", descripcion_template: "Notificación del servicio {servicio} para {entidad}." }); setPreview(null); }}>+ Nueva</button>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="space-y-2"><label className="text-sm font-semibold">Fase</label>
          <select className="w-full h-10 rounded-xl border border-input bg-background px-3 text-sm" value={reglaForm.fase} onChange={e => setReglaForm(f => ({ ...f, fase: e.target.value }))}>
            <option value="APERTURA">APERTURA</option><option value="CIERRE">CIERRE</option>
            <option value="MANTENIMIENTO">MANTENIMIENTO</option><option value="FIN_MANTENIMIENTO">FIN_MANTENIMIENTO</option>
          </select></div>
        <div className="space-y-2"><label className="text-sm font-semibold">Plataforma</label>
          <select className="w-full h-10 rounded-xl border border-input bg-background px-3 text-sm" value={reglaForm.plataforma_id} onChange={e => setReglaForm(f => ({ ...f, plataforma_id: e.target.value }))}>
            <option value="">(Cualquier Plataforma)</option>
            {catalogos?.plataformas?.map((p: any) => <option key={p.id} value={String(p.id)}>{p.nombre}</option>)}
          </select></div>
        <div className="space-y-2"><label className="text-sm font-semibold">Servicio</label>
          <select className="w-full h-10 rounded-xl border border-input bg-background px-3 text-sm" value={reglaForm.servicio_id} onChange={e => setReglaForm(f => ({ ...f, servicio_id: e.target.value }))}>
            <option value="">(Cualquier Servicio)</option>
            {catalogos?.servicios?.map((s: any) => <option key={s.id} value={String(s.id)}>{s.nombre}</option>)}
          </select></div>
      </div>
      <div className="space-y-2"><label className="text-sm font-semibold">Asunto Template</label>
        <Input value={reglaForm.asunto_template} onChange={e => setReglaForm(f => ({ ...f, asunto_template: e.target.value }))} /></div>
      <div className="space-y-2"><label className="text-sm font-semibold">Descripción Template</label>
        <Textarea value={reglaForm.descripcion_template} onChange={e => setReglaForm(f => ({ ...f, descripcion_template: e.target.value }))} rows={3} /></div>
      <div className="flex gap-3">
        <Button onClick={guardarRegla} className="gap-2"><Save size={16} /> {editingId ? "Actualizar Regla" : "Guardar Regla"}</Button>
        <Button variant="outline" onClick={previsualizar} className="gap-2"><Eye size={16} /> Previsualizar</Button>
      </div>

      {preview && (
        <div className="rounded-xl border bg-muted/30 p-4">
          <h4 className="font-semibold text-accent mb-2">Preview</h4>
          <p className="text-sm"><strong>Entidad:</strong> {preview.entidad_formateada || preview.entidad_afectada}</p>
          <p className="text-sm"><strong>Asunto:</strong> {preview.asunto_template}</p>
          <p className="text-sm"><strong>Descripción:</strong> {preview.descripcion_template}</p>
        </div>
      )}

      {reglas.length > 0 && (
        <div>
          <div className="flex items-center gap-3 mb-3">
            <h4 className="font-semibold text-accent">Reglas ({reglasFiltradas.length})</h4>
            <div className="relative flex-1 max-w-xs">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <Input className="pl-8 h-9 text-sm" placeholder="Buscar reglas..." value={busqueda} onChange={e => setBusqueda(e.target.value)} />
            </div>
          </div>
          <DataTable columns={[
            { key: "id", header: "ID" },
            { key: "fase", header: "Fase", render: (item: any) => <Badge variant="info">{item.fase}</Badge> },
            { key: "plat_nom", header: "Plataforma" },
            { key: "serv_nom", header: "Servicio" },
            { key: "asunto_template", header: "Asunto", render: (item: any) => <span className="text-xs truncate max-w-[180px] block">{item.asunto_template}</span> },
            { key: "acciones", header: "", render: (item: any) => (
              <div className="flex gap-1">
                <Button variant="ghost" size="sm" onClick={() => cargarRegla(item)}><Edit3 size={14} /></Button>
                <Button variant="ghost" size="sm" onClick={() => eliminarRegla(item.id)}><Trash2 size={14} className="text-red-500" /></Button>
              </div>
            )}
          ]} data={reglasFiltradas} />
        </div>
      )}
    </div>
  );
}

function RolesPermisos() {
  const [roles, setRoles] = useState<string[]>([]);
  const [selectedRol, setSelectedRol] = useState("");
  const [permisos, setPermisos] = useState<any>({});
  const [servicios, setServicios] = useState<any[]>([]);
  const [serviciosSel, setServiciosSel] = useState<number[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.get<string[]>("/admin/roles"),
      api.get<any[]>("/admin/servicios")
    ]).then(([r, s]) => {
      setRoles(r);
      setServicios(s.filter((x: any) => x.estado !== false));
      if (r.length) setSelectedRol(r[0]);
    }).catch(console.error).finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selectedRol) return;
    api.get<any>(`/admin/roles/${selectedRol}`).then(r => {
      setPermisos(r);
      setServiciosSel(r.servicios_restringidos || []);
    }).catch(console.error);
  }, [selectedRol]);

  const togglePermiso = (key: string) => {
    setPermisos((prev: any) => ({
      ...prev,
      permisos: { ...prev.permisos, [key]: !prev.permisos?.[key] }
    }));
  };

  const toggleServicioRestringido = (servId: number) => {
    setServiciosSel(prev =>
      prev.includes(servId) ? prev.filter(id => id !== servId) : [...prev, servId]
    );
  };

  const guardar = async () => {
    try {
      await api.put(`/admin/roles/${selectedRol}`, {
        ver_aprobaciones: permisos.permisos?.ver_aprobaciones || false,
        ver_apertura: permisos.permisos?.ver_apertura ?? true,
        ver_cierre: permisos.permisos?.ver_cierre ?? true,
        ver_mantenimiento: permisos.permisos?.ver_mantenimiento ?? true,
        ver_edicion: permisos.permisos?.ver_edicion ?? true,
        ver_reportes: permisos.permisos?.ver_reportes ?? true,
        ver_admin: permisos.permisos?.ver_admin || false,
        puede_aprobar: permisos.permisos?.puede_aprobar || false,
        ver_solo_propios: permisos.permisos?.ver_solo_propios || false,
        exige_aprobacion: permisos.permisos?.exige_aprobacion || false,
        servicios_restringidos: serviciosSel
      });
      toast.success(`Permisos actualizados para rol ${selectedRol}`);
    } catch (e: any) {
      toast.error(e.message || "Error al actualizar permisos");
    }
  };

  const permisosList = [
    { key: "ver_aprobaciones", label: "Bandeja Aprobaciones" },
    { key: "ver_apertura", label: "Apertura Novedad" },
    { key: "ver_cierre", label: "Cierre Novedad" },
    { key: "ver_mantenimiento", label: "Mantenimientos" },
    { key: "ver_edicion", label: "Editar / Historial" },
    { key: "ver_reportes", label: "Informes y Métricas" },
    { key: "ver_admin", label: "Panel Administración" },
    { key: "puede_aprobar", label: "Capacidad de Aprobar" },
    { key: "exige_aprobacion", label: "Exige Aprobación" },
    { key: "ver_solo_propios", label: "Solo Propios" },
  ];

  if (loading) return <div className="py-8 text-center text-muted-foreground">Cargando roles...</div>;

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <label className="text-sm font-semibold">Seleccionar Rol</label>
        <div className="flex gap-3 items-center">
          <select className="w-full max-w-xs h-10 rounded-xl border border-input bg-background px-3 text-sm"
            value={selectedRol} onChange={e => setSelectedRol(e.target.value)}>
            {roles.map(r => <option key={r} value={r}>{r}</option>)}
          </select>
          <span className="text-xs text-muted-foreground">
            Permisos para: <strong>{selectedRol}</strong>
          </span>
        </div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {permisosList.map(p => (
          <label key={p.key} className="flex items-center gap-2 text-sm cursor-pointer p-2 rounded-lg hover:bg-muted/50">
            <input type="checkbox" checked={permisos.permisos?.[p.key] || false}
              onChange={() => togglePermiso(p.key)} className="rounded border-gray-300 w-4 h-4" />
            {p.label}
          </label>
        ))}
      </div>

      <div className="space-y-2 pt-2 border-t">
        <label className="text-sm font-semibold">Restringir acceso SÓLO a estos servicios (vacío = Todos)</label>
        <div className="flex flex-wrap gap-2 max-h-40 overflow-y-auto p-2 border rounded-xl">
          {servicios.length === 0 && <p className="text-xs text-muted-foreground p-2">No hay servicios activos</p>}
          {servicios.map((s: any) => (
            <label key={s.id} className="flex items-center gap-1.5 text-sm cursor-pointer p-1.5 rounded-lg hover:bg-muted/50">
              <input type="checkbox" checked={serviciosSel.includes(s.id)}
                onChange={() => toggleServicioRestringido(s.id)} className="rounded border-gray-300 w-3.5 h-3.5" />
              {s.nombre}
            </label>
          ))}
        </div>
        {serviciosSel.length > 0 && (
          <p className="text-xs text-amber-600">{serviciosSel.length} servicio(s) seleccionado(s) como restringidos</p>
        )}
      </div>

      <div className="flex items-center gap-4 pt-2">
        <Button onClick={guardar} className="gap-2"><Save size={16} /> Guardar Permisos</Button>
        {serviciosSel.length > 0 && <Badge variant="warning">Acceso restringido a servicios específicos</Badge>}
      </div>
    </div>
  );
}

function ServiciosAdmin() {
  const [servicios, setServicios] = useState<any[]>([]);
  const [nombre, setNombre] = useState("");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editNombre, setEditNombre] = useState("");
  const [loading, setLoading] = useState(true);
  const [busqueda, setBusqueda] = useState("");

  useEffect(() => {
    api.get<any[]>("/admin/servicios").then(setServicios).catch(console.error).finally(() => setLoading(false));
  }, []);

  const crear = async () => {
    if (!nombre.trim()) { toast.error("Ingresa un nombre"); return; }
    try {
      await api.post("/admin/servicios", { nombre: nombre.trim() });
      toast.success("Servicio creado");
      setNombre("");
      setServicios(await api.get<any[]>("/admin/servicios"));
    } catch (e: any) {
      toast.error(e.message || "Error al crear");
    }
  };

  const toggleEstado = async (item: any) => {
    try {
      await api.put(`/admin/servicios/${item.id}?estado=${!item.estado}`, { nombre: item.nombre });
      toast.success(`Servicio ${item.estado ? "desactivado" : "activado"}`);
      setServicios(await api.get<any[]>("/admin/servicios"));
    } catch (e: any) {
      toast.error(e.message || "Error al actualizar");
    }
  };

  const guardarEdit = async (id: number) => {
    if (!editNombre.trim()) { toast.error("El nombre no puede estar vacío"); return; }
    try {
      await api.put(`/admin/servicios/${id}`, { nombre: editNombre.trim() });
      toast.success("Servicio actualizado");
      setEditingId(null);
      setServicios(await api.get<any[]>("/admin/servicios"));
    } catch (e: any) {
      toast.error(e.message || "Error al actualizar");
    }
  };

  const filtrados = servicios.filter(s =>
    !busqueda || s.nombre?.toLowerCase().includes(busqueda.toLowerCase())
  );

  return (
    <div className="space-y-4">
      <div className="flex gap-3">
        <Input placeholder="Nombre del nuevo servicio" className="max-w-xs" value={nombre} onChange={e => setNombre(e.target.value)} />
        <Button onClick={crear} className="gap-2"><Plus size={16} /> Crear Servicio</Button>
      </div>
      {loading ? <p className="text-sm text-muted-foreground">Cargando...</p> : (
        <>
          <div className="relative max-w-xs">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <Input className="pl-8 h-9 text-sm" placeholder="Buscar servicio..." value={busqueda} onChange={e => setBusqueda(e.target.value)} />
          </div>
          <DataTable columns={[
            { key: "id", header: "ID" },
            { key: "nombre", header: "Nombre", render: (item: any) => editingId === item.id ? (
              <div className="flex gap-2">
                <Input value={editNombre} onChange={e => setEditNombre(e.target.value)} className="h-8 text-sm max-w-[200px]" />
                <Button size="sm" onClick={() => guardarEdit(item.id)}><Save size={14} /></Button>
                <Button size="sm" variant="ghost" onClick={() => setEditingId(null)}><XCircle size={14} /></Button>
              </div>
            ) : (
              <span className="cursor-pointer hover:text-primary" onClick={() => { setEditingId(item.id); setEditNombre(item.nombre); }}>{item.nombre} <Edit3 size={12} className="inline opacity-40" /></span>
            )},
            { key: "estado", header: "Estado", render: (item: any) => (
              <button onClick={() => toggleEstado(item)} className="flex items-center gap-1 text-sm">
                {item.estado ? <ToggleRight size={18} className="text-green-600" /> : <ToggleLeft size={18} className="text-red-400" />}
                <Badge variant={item.estado ? "success" : "danger"}>{item.estado ? "Activo" : "Inactivo"}</Badge>
              </button>
            )}
          ]} data={filtrados} />
        </>
      )}
    </div>
  );
}

function TercerosAdmin() {
  const [terceros, setTerceros] = useState<any[]>([]);
  const [nombre, setNombre] = useState("");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editNombre, setEditNombre] = useState("");
  const [loading, setLoading] = useState(true);
  const [busqueda, setBusqueda] = useState("");

  useEffect(() => {
    api.get<any[]>("/admin/terceros").then(setTerceros).catch(console.error).finally(() => setLoading(false));
  }, []);

  const crear = async () => {
    if (!nombre.trim()) { toast.error("Ingresa un nombre"); return; }
    try {
      await api.post("/admin/terceros", { nombre: nombre.trim() });
      toast.success("Tercero creado");
      setNombre("");
      setTerceros(await api.get<any[]>("/admin/terceros"));
    } catch (e: any) {
      toast.error(e.message || "Error al crear");
    }
  };

  const toggleEstado = async (item: any) => {
    try {
      await api.put(`/admin/terceros/${item.id}?estado=${!item.estado}`, { nombre: item.nombre });
      toast.success(`Tercero ${item.estado ? "desactivado" : "activado"}`);
      setTerceros(await api.get<any[]>("/admin/terceros"));
    } catch (e: any) {
      toast.error(e.message || "Error al actualizar");
    }
  };

  const guardarEdit = async (id: number) => {
    if (!editNombre.trim()) { toast.error("El nombre no puede estar vacío"); return; }
    try {
      await api.put(`/admin/terceros/${id}`, { nombre: editNombre.trim() });
      toast.success("Tercero actualizado");
      setEditingId(null);
      setTerceros(await api.get<any[]>("/admin/terceros"));
    } catch (e: any) {
      toast.error(e.message || "Error al actualizar");
    }
  };

  const filtrados = terceros.filter(t =>
    !busqueda || t.nombre?.toLowerCase().includes(busqueda.toLowerCase())
  );

  return (
    <div className="space-y-4">
      <div className="flex gap-3">
        <Input placeholder="Nombre del nuevo tercero" className="max-w-xs" value={nombre} onChange={e => setNombre(e.target.value)} />
        <Button onClick={crear} className="gap-2"><Plus size={16} /> Crear Tercero</Button>
      </div>
      {loading ? <p className="text-sm text-muted-foreground">Cargando...</p> : (
        <>
          <div className="relative max-w-xs">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <Input className="pl-8 h-9 text-sm" placeholder="Buscar tercero..." value={busqueda} onChange={e => setBusqueda(e.target.value)} />
          </div>
          <DataTable columns={[
            { key: "id", header: "ID" },
            { key: "nombre", header: "Nombre", render: (item: any) => editingId === item.id ? (
              <div className="flex gap-2">
                <Input value={editNombre} onChange={e => setEditNombre(e.target.value)} className="h-8 text-sm max-w-[200px]" />
                <Button size="sm" onClick={() => guardarEdit(item.id)}><Save size={14} /></Button>
                <Button size="sm" variant="ghost" onClick={() => setEditingId(null)}><XCircle size={14} /></Button>
              </div>
            ) : (
              <span className="cursor-pointer hover:text-primary" onClick={() => { setEditingId(item.id); setEditNombre(item.nombre); }}>{item.nombre} <Edit3 size={12} className="inline opacity-40" /></span>
            )},
            { key: "estado", header: "Estado", render: (item: any) => (
              <button onClick={() => toggleEstado(item)} className="flex items-center gap-1 text-sm">
                {item.estado ? <ToggleRight size={18} className="text-green-600" /> : <ToggleLeft size={18} className="text-red-400" />}
                <Badge variant={item.estado ? "success" : "danger"}>{item.estado ? "Activo" : "Inactivo"}</Badge>
              </button>
            )}
          ]} data={filtrados} />
        </>
      )}
    </div>
  );
}

function VinculosAdmin() {
  const [vinculos, setVinculos] = useState<any[]>([]);
  const [servicios, setServicios] = useState<any[]>([]);
  const [terceros, setTerceros] = useState<any[]>([]);
  const [servicioId, setServicioId] = useState("");
  const [terceroId, setTerceroId] = useState("");
  const [loading, setLoading] = useState(true);
  const [busqueda, setBusqueda] = useState("");

  const loadData = () => Promise.all([
    api.get<any[]>("/admin/vinculos"),
    api.get<any[]>("/admin/servicios"),
    api.get<any[]>("/admin/terceros")
  ]).then(([v, s, t]) => { setVinculos(v.filter((x: any) => x.estado !== false || x.estado === undefined)); setServicios(s.filter((x: any) => x.estado !== false)); setTerceros(t.filter((x: any) => x.estado !== false)); })
    .catch(console.error).finally(() => setLoading(false));

  useEffect(() => { loadData(); }, []);

  const vincular = async () => {
    if (!servicioId || !terceroId) { toast.error("Selecciona servicio y tercero"); return; }
    try {
      await api.post("/admin/vinculos", { servicio_id: Number(servicioId), tercero_id: Number(terceroId) });
      toast.success("Vínculo creado");
      setServicioId(""); setTerceroId("");
      loadData();
    } catch (e: any) {
      toast.error(e.message || "Error al vincular");
    }
  };

  const eliminar = async (id: number) => {
    if (!(await confirmAction("¿Eliminar este vínculo?"))) return;
    try {
      await api.delete(`/admin/vinculos/${id}`);
      toast.success("Vínculo eliminado");
      setVinculos(vinculos.filter(v => v.id !== id));
    } catch (e: any) {
      toast.error(e.message || "Error al eliminar");
    }
  };

  const filtrados = vinculos.filter(v =>
    !busqueda || v.servicio_nom?.toLowerCase().includes(busqueda.toLowerCase()) ||
    v.tercero_nom?.toLowerCase().includes(busqueda.toLowerCase())
  );

  if (loading) return <div className="py-8 text-center text-muted-foreground">Cargando...</div>;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="space-y-2"><label className="text-sm font-semibold">Servicio</label>
          <select className="w-full h-10 rounded-xl border border-input bg-background px-3 text-sm" value={servicioId} onChange={e => setServicioId(e.target.value)}>
            <option value="">Seleccionar...</option>
            {servicios.map((s: any) => <option key={s.id} value={String(s.id)}>{s.nombre}</option>)}
          </select></div>
        <div className="space-y-2"><label className="text-sm font-semibold">Tercero</label>
          <select className="w-full h-10 rounded-xl border border-input bg-background px-3 text-sm" value={terceroId} onChange={e => setTerceroId(e.target.value)}>
            <option value="">Seleccionar...</option>
            {terceros.map((t: any) => <option key={t.id} value={String(t.id)}>{t.nombre}</option>)}
          </select></div>
      </div>
      <Button onClick={vincular} className="gap-2"><Link2 size={16} /> Vincular</Button>

      {vinculos.length > 0 && (
        <div className="mt-4">
          <div className="flex items-center gap-3 mb-3">
            <h4 className="font-semibold text-accent">Vínculos ({filtrados.length})</h4>
            <div className="relative flex-1 max-w-xs">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <Input className="pl-8 h-9 text-sm" placeholder="Buscar vínculo..." value={busqueda} onChange={e => setBusqueda(e.target.value)} />
            </div>
          </div>
          <DataTable columns={[
            { key: "servicio_nom", header: "Servicio" },
            { key: "tercero_nom", header: "Tercero" },
            { key: "acciones", header: "", render: (item: any) => <Button variant="ghost" size="sm" onClick={() => eliminar(item.id)}><Trash2 size={14} className="text-red-500" /></Button> }
          ]} data={filtrados} />
        </div>
      )}
    </div>
  );
}

function CorreosServicio() {
  const [servicios, setServicios] = useState<any[]>([]);
  const [servicioId, setServicioId] = useState("");
  const [correos, setCorreos] = useState<any[]>([]);
  const [form, setForm] = useState({ email: "", nombre: "", plataforma_id: "", tercero_id: "" });
  const [catalogos, setCatalogos] = useState<any>(null);
  const [terceros, setTerceros] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api.get<any[]>("/admin/servicios"), api.get<any>("/comunicados/catalogos"), api.get<any[]>("/admin/terceros")])
      .then(([s, c, t]) => { setServicios(s.filter((x: any) => x.estado !== false)); setCatalogos(c); setTerceros(t.filter((x: any) => x.estado !== false)); })
      .catch(console.error).finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!servicioId) { setCorreos([]); return; }
    api.get<any[]>(`/admin/correos-servicio/${servicioId}`).then(setCorreos).catch(console.error);
  }, [servicioId]);

  const agregar = async () => {
    if (!form.email || !servicioId) { toast.error("Completa los campos requeridos"); return; }
    try {
      await api.post("/admin/correos-servicio", {
        servicio_id: Number(servicioId), email: form.email.trim(),
        nombre: form.nombre.trim() || null,
        plataforma_id: form.plataforma_id ? Number(form.plataforma_id) : null,
        tercero_id: form.tercero_id ? Number(form.tercero_id) : null
      });
      toast.success("Correo agregado al servicio");
      setForm({ email: "", nombre: "", plataforma_id: "", tercero_id: "" });
      setCorreos(await api.get<any[]>(`/admin/correos-servicio/${servicioId}`));
    } catch (e: any) {
      toast.error(e.message || "Error al agregar correo");
    }
  };

  const eliminarCorreo = async (id: number) => {
    if (!(await confirmAction("¿Eliminar este correo del servicio?"))) return;
    try {
      await api.delete(`/admin/correos-servicio/${id}`);
      toast.success("Correo eliminado");
      setCorreos(correos.filter(c => c.id !== id));
    } catch (e: any) {
      toast.error(e.message || "Error al eliminar");
    }
  };

  if (loading) return <div className="py-8 text-center text-muted-foreground">Cargando...</div>;

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <label className="text-sm font-semibold">Seleccionar Servicio</label>
        <select className="w-full h-10 rounded-xl border border-input bg-background px-3 text-sm max-w-xs"
          value={servicioId} onChange={e => setServicioId(e.target.value)}>
          <option value="">Seleccionar servicio...</option>
          {servicios.map((s: any) => <option key={s.id} value={String(s.id)}>{s.nombre}</option>)}
        </select>
      </div>

      {servicioId && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2"><label className="text-sm font-semibold">Email *</label>
              <Input value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))} placeholder="correo@empresa.com" /></div>
            <div className="space-y-2"><label className="text-sm font-semibold">Nombre (opcional)</label>
              <Input value={form.nombre} onChange={e => setForm(f => ({ ...f, nombre: e.target.value }))} placeholder="Nombre del contacto" /></div>
            <div className="space-y-2"><label className="text-sm font-semibold">Plataforma</label>
              <select className="w-full h-10 rounded-xl border border-input bg-background px-3 text-sm" value={form.plataforma_id} onChange={e => setForm(f => ({ ...f, plataforma_id: e.target.value }))}>
                <option value="">(Sin plataforma)</option>
                {catalogos?.plataformas?.map((p: any) => <option key={p.id} value={String(p.id)}>{p.nombre}</option>)}
              </select></div>
            <div className="space-y-2"><label className="text-sm font-semibold">Tercero</label>
              <select className="w-full h-10 rounded-xl border border-input bg-background px-3 text-sm" value={form.tercero_id} onChange={e => setForm(f => ({ ...f, tercero_id: e.target.value }))}>
                <option value="">(Sin tercero)</option>
                {terceros.map((t: any) => <option key={t.id} value={String(t.id)}>{t.nombre}</option>)}
              </select></div>
          </div>
          <Button onClick={agregar} className="gap-2"><Plus size={16} /> Agregar Correo</Button>

          {correos.length > 0 && (
            <div className="mt-4">
              <h4 className="font-semibold text-accent mb-3">Correos del Servicio ({correos.length})</h4>
              <DataTable columns={[
                { key: "email", header: "Email" },
                { key: "nombre", header: "Nombre" },
                { key: "plataforma_nom", header: "Plataforma" },
                { key: "tercero_nom", header: "Tercero" },
                { key: "estado", header: "Estado", render: (item: any) => <Badge variant={item.estado ? "success" : "danger"}>{item.estado ? "Activo" : "Inactivo"}</Badge> },
                { key: "acciones", header: "", render: (item: any) => <Button variant="ghost" size="sm" onClick={() => eliminarCorreo(item.id)}><Trash2 size={14} className="text-red-500" /></Button> }
              ]} data={correos} />
            </div>
          )}
        </>
      )}
    </div>
  );
}

function CorreosInternos() {
  const [correos, setCorreos] = useState<any[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get<any[]>("/admin/correos-internos").then(setCorreos).catch(console.error).finally(() => setLoading(false));
  }, []);

  const agregar = async () => {
    if (!input.trim()) { toast.error("Ingresa al menos un correo"); return; }
    const validos = input.split(/[\n,]/).map(e => e.trim()).filter(e => e);
    try {
      await api.post("/admin/correos-internos", { emails: validos.join(",") });
      toast.success(`${validos.length} correo(s) guardado(s)`);
      setInput("");
      setCorreos(await api.get<any[]>("/admin/correos-internos"));
    } catch (e: any) {
      toast.error(e.message || "Error al guardar");
    }
  };

  const eliminar = async (id: number) => {
    if (!(await confirmAction("¿Eliminar este correo interno?"))) return;
    try {
      await api.delete(`/admin/correos-internos/${id}`);
      toast.success("Correo eliminado");
      setCorreos(correos.filter(c => c.id !== id));
    } catch (e: any) {
      toast.error(e.message || "Error al eliminar");
    }
  };

  if (loading) return <div className="py-8 text-center text-muted-foreground">Cargando...</div>;

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <label className="text-sm font-semibold">Agregar Correos (separados por coma o salto de línea)</label>
        <Textarea value={input} onChange={e => setInput(e.target.value)} rows={3} placeholder="correo1@empresa.com, correo2@empresa.com" />
      </div>
      <Button onClick={agregar} className="gap-2"><Plus size={16} /> Agregar Correos</Button>

      {correos.length > 0 && (
        <div className="mt-4">
          <h4 className="font-semibold text-accent mb-3">Correos Internos (CC) - {correos.length}</h4>
          <DataTable columns={[
            { key: "email", header: "Email" },
            { key: "estado", header: "Estado", render: (item: any) => <Badge variant={item.estado ? "success" : "danger"}>{item.estado ? "Activo" : "Inactivo"}</Badge> },
            { key: "acciones", header: "", render: (item: any) => <Button variant="ghost" size="sm" onClick={() => eliminar(item.id)}><Trash2 size={14} className="text-red-500" /></Button> }
          ]} data={correos} />
        </div>
      )}
    </div>
  );
}

function UsuariosAdmin() {
  const [usuarios, setUsuarios] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ nombre: "", apellido: "", correo: "", password: "", rol: "Monitoreo" });

  useEffect(() => {
    api.get<any[]>("/admin/usuarios").then(setUsuarios).catch(console.error).finally(() => setLoading(false));
  }, []);

  const crear = async () => {
    if (!form.nombre || !form.apellido || !form.correo || !form.password) {
      toast.error("Completa todos los campos"); return;
    }
    try {
      await api.post("/admin/usuarios", form);
      toast.success(`Usuario ${form.correo} creado`);
      setShowForm(false);
      setForm({ nombre: "", apellido: "", correo: "", password: "", rol: "Monitoreo" });
      setUsuarios(await api.get<any[]>("/admin/usuarios"));
    } catch (e: any) {
      toast.error(e.message || "Error al crear usuario");
    }
  };

  const toggleEstado = async (user: any) => {
    try {
      await api.put(`/admin/usuarios/${user.id}`, { estado: !user.estado });
      toast.success(`Usuario ${user.estado ? "desactivado" : "activado"}`);
      setUsuarios(await api.get<any[]>("/admin/usuarios"));
    } catch (e: any) {
      toast.error(e.message || "Error al actualizar");
    }
  };

  const cambiarRol = async (userId: number, nuevoRol: string) => {
    try {
      await api.put(`/admin/usuarios/${userId}`, { rol: nuevoRol });
      toast.success("Rol actualizado");
      setUsuarios(await api.get<any[]>("/admin/usuarios"));
    } catch (e: any) {
      toast.error(e.message || "Error al actualizar rol");
    }
  };

  if (loading) return <div className="py-8 text-center text-muted-foreground">Cargando...</div>;

  return (
    <div className="space-y-4">
      {!showForm ? (
        <Button onClick={() => setShowForm(true)} className="gap-2"><Plus size={16} /> Crear Usuario</Button>
      ) : (
        <div className="space-y-4 rounded-xl border p-4 bg-muted/20">
          <div className="flex items-center justify-between">
            <h4 className="font-semibold text-accent">Nuevo Usuario</h4>
            <Button variant="ghost" size="sm" onClick={() => setShowForm(false)}><XCircle size={14} /> Cancelar</Button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2"><label className="text-sm font-semibold">Nombre</label>
              <Input value={form.nombre} onChange={e => setForm(f => ({ ...f, nombre: e.target.value }))} /></div>
            <div className="space-y-2"><label className="text-sm font-semibold">Apellido</label>
              <Input value={form.apellido} onChange={e => setForm(f => ({ ...f, apellido: e.target.value }))} /></div>
            <div className="space-y-2"><label className="text-sm font-semibold">Correo</label>
              <Input type="email" value={form.correo} onChange={e => setForm(f => ({ ...f, correo: e.target.value }))} /></div>
            <div className="space-y-2"><label className="text-sm font-semibold">Contraseña</label>
              <Input type="password" value={form.password} onChange={e => setForm(f => ({ ...f, password: e.target.value }))} /></div>
            <div className="space-y-2"><label className="text-sm font-semibold">Rol</label>
              <select className="w-full h-10 rounded-xl border border-input bg-background px-3 text-sm" value={form.rol} onChange={e => setForm(f => ({ ...f, rol: e.target.value }))}>
                <option value="Monitoreo">Monitoreo</option><option value="Lider">Lider</option>
                <option value="Administrador">Administrador</option><option value="Corporate">Corporate</option>
              </select></div>
          </div>
          <Button onClick={crear} className="gap-2"><Save size={16} /> Guardar Usuario</Button>
        </div>
      )}

      <DataTable columns={[
        { key: "id", header: "ID" },
        { key: "nombre", header: "Nombre", render: (item: any) => `${item.nombre} ${item.apellido}` },
        { key: "correo", header: "Correo" },
        { key: "rol", header: "Rol", render: (item: any) => (
          <select className="text-xs border rounded-md px-2 py-1 bg-background" value={item.rol} onChange={e => cambiarRol(item.id, e.target.value)}>
            <option value="Monitoreo">Monitoreo</option><option value="Lider">Lider</option>
            <option value="Administrador">Administrador</option><option value="Corporate">Corporate</option>
          </select>
        )},
        { key: "estado", header: "Estado", render: (item: any) => (
          <button onClick={() => toggleEstado(item)} className="flex items-center gap-1">
            {item.estado ? <ToggleRight size={18} className="text-green-600" /> : <ToggleLeft size={18} className="text-red-400" />}
            <Badge variant={item.estado ? "success" : "danger"}>{item.estado ? "Activo" : "Inactivo"}</Badge>
          </button>
        )}
      ]} data={usuarios} />
    </div>
  );
}

function PlantillasAdmin() {
  const [plantillas, setPlantillas] = useState<any[]>([]);
  const [catalogos, setCatalogos] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState("");
  const [form, setForm] = useState({ plataforma_id: "", tipo_comunicado_id: "", asunto: "", html: "" });
  const [previewHtml, setPreviewHtml] = useState("");

  const loadPlantillas = () => api.get<any[]>("/admin/plantillas").then(setPlantillas);
  useEffect(() => {
    Promise.all([loadPlantillas(), api.get<any>("/comunicados/catalogos")])
      .then(([p, c]) => { setCatalogos(c); })
      .catch(console.error).finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selectedId) { setForm({ plataforma_id: "", tipo_comunicado_id: "", asunto: "", html: "" }); setPreviewHtml(""); return; }
    const plant = plantillas.find((p: any) => String(p.id) === selectedId);
    if (plant) {
      setForm({ plataforma_id: String(plant.plataforma_id || ""), tipo_comunicado_id: String(plant.tipo_comunicado_id || ""), asunto: plant.asunto || "", html: plant.html || "" });
      const preview = plant.html?.replace(/\{\{ consecutivo \}\}/g, "PRE-123")
        .replace(/\{\{ servicio \}\}/g, "Servicio Ejemplo")
        .replace(/\{\{ descripcion \}\}/g, "Descripción de ejemplo")
        .replace(/\{\{ cliente \}\}/g, "Cliente Ejemplo") || "";
      setPreviewHtml(preview);
    }
  }, [selectedId, plantillas]);

  const guardar = async () => {
    if (!form.asunto || !form.html) { toast.error("Completa asunto y HTML"); return; }
    try {
      const body = {
        plataforma_id: form.plataforma_id ? Number(form.plataforma_id) : null,
        tipo_comunicado_id: Number(form.tipo_comunicado_id),
        asunto: form.asunto, html: form.html
      };
      if (selectedId) {
        await api.put(`/admin/plantillas/${selectedId}`, body);
        toast.success("Plantilla actualizada");
      } else {
        await api.post("/admin/plantillas", body);
        toast.success("Plantilla creada");
      }
      await loadPlantillas();
    } catch (e: any) {
      toast.error(e.message || "Error al guardar plantilla");
    }
  };

  if (loading) return <div className="py-8 text-center text-muted-foreground">Cargando...</div>;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="space-y-2"><label className="text-sm font-semibold">Seleccionar Plantilla</label>
          <select className="w-full h-10 rounded-xl border border-input bg-background px-3 text-sm" value={selectedId} onChange={e => setSelectedId(e.target.value)}>
            <option value="">(Nueva Plantilla)</option>
            {plantillas.map((p: any) => <option key={p.id} value={String(p.id)}>{p.asunto}</option>)}
          </select></div>
        <div className="space-y-2"><label className="text-sm font-semibold">Tipo Comunicado</label>
          <select className="w-full h-10 rounded-xl border border-input bg-background px-3 text-sm" value={form.tipo_comunicado_id} onChange={e => setForm(f => ({ ...f, tipo_comunicado_id: e.target.value }))}>
            <option value="">Seleccionar...</option>
            {catalogos?.tipos?.map((t: any) => <option key={t.id} value={String(t.id)}>{t.nombre}</option>)}
          </select></div>
      </div>
      <div className="space-y-2"><label className="text-sm font-semibold">Asunto</label>
        <Input value={form.asunto} onChange={e => setForm(f => ({ ...f, asunto: e.target.value }))} /></div>
      <div className="space-y-2"><label className="text-sm font-semibold">Código HTML</label>
        <Textarea value={form.html} onChange={e => setForm(f => ({ ...f, html: e.target.value }))} rows={12} className="font-mono text-xs" /></div>
      <div className="flex gap-3">
        <Button onClick={guardar} className="gap-2"><Save size={16} /> {selectedId ? "Actualizar Plantilla" : "Guardar Plantilla"}</Button>
        {form.html && (
          <Button variant="outline" onClick={() => { const w = window.open('', '_blank'); if (w) { w.document.write(form.html); } }} className="gap-2"><Eye size={16} /> Previsualizar</Button>
        )}
      </div>
      {previewHtml && selectedId && (
        <div className="rounded-xl border overflow-hidden" style={{ height: 350 }}>
          <iframe srcDoc={previewHtml} width="100%" height="100%" style={{ border: "none" }} title="Preview" />
        </div>
      )}
    </div>
  );
}

function AuditoriaAdmin() {
  const [logs, setLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [filtroAccion, setFiltroAccion] = useState("");
  const [filtroAnalista, setFiltroAnalista] = useState("");
  const [filtroFecha, setFiltroFecha] = useState("");

  useEffect(() => {
    api.get<any[]>("/admin/auditoria").then(setLogs).catch(console.error).finally(() => setLoading(false));
  }, []);

  const accionesUnicas = [...new Set(logs.map(l => l.accion))].sort();
  const analistasUnicos = [...new Set(logs.map(l => l.analista).filter(Boolean))].sort();

  const filtrados = logs.filter(l => {
    if (filtroAccion && l.accion !== filtroAccion) return false;
    if (filtroAnalista && l.analista !== filtroAnalista) return false;
    if (filtroFecha) {
      const logDate = new Date(l.fecha).toISOString().split("T")[0];
      if (logDate !== filtroFecha) return false;
    }
    return true;
  });

  if (loading) return <div className="py-8 text-center text-muted-foreground">Cargando auditoría...</div>;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-3 items-end">
        <div className="space-y-1">
          <label className="text-xs font-semibold text-muted-foreground">Acción</label>
          <select className="h-9 rounded-lg border border-input bg-background px-2 text-sm" value={filtroAccion} onChange={e => setFiltroAccion(e.target.value)}>
            <option value="">Todas</option>
            {accionesUnicas.map(a => <option key={a} value={a}>{a}</option>)}
          </select>
        </div>
        <div className="space-y-1">
          <label className="text-xs font-semibold text-muted-foreground">Analista</label>
          <select className="h-9 rounded-lg border border-input bg-background px-2 text-sm" value={filtroAnalista} onChange={e => setFiltroAnalista(e.target.value)}>
            <option value="">Todos</option>
            {analistasUnicos.map(a => <option key={a} value={a}>{a}</option>)}
          </select>
        </div>
        <div className="space-y-1">
          <label className="text-xs font-semibold text-muted-foreground">Fecha</label>
          <Input type="date" className="h-9 text-sm" value={filtroFecha} onChange={e => setFiltroFecha(e.target.value)} />
        </div>
        <Button variant="ghost" size="sm" onClick={() => { setFiltroAccion(""); setFiltroAnalista(""); setFiltroFecha(""); }} className="h-9">
          <XCircle size={14} /> Limpiar
        </Button>
        <span className="text-xs text-muted-foreground ml-auto">{filtrados.length} de {logs.length} registros</span>
      </div>

      {filtrados.length === 0 ? (
        <div className="rounded-xl border bg-muted/30 p-8 text-center text-muted-foreground">
          <p>No hay registros de auditoría con esos filtros.</p>
        </div>
      ) : (
        <DataTable columns={[
          { key: "fecha", header: "Fecha/Hora", render: (item: any) => new Date(item.fecha).toLocaleString("es-CO") },
          { key: "analista", header: "Analista" },
          { key: "accion", header: "Acción", render: (item: any) => (
            <Badge variant={item.accion?.startsWith("ADMIN") ? "warning" : item.accion?.startsWith("SISTEMA") ? "danger" : "info"}>{item.accion}</Badge>
          )},
          { key: "detalles", header: "Detalles" }
        ]} data={filtrados} />
      )}
    </div>
  );
}
