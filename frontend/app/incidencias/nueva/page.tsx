"use client";

import { useState, useEffect, useCallback } from "react";
import { AppShell } from "@/components/layout/app-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { PageLoader, EmptyState } from "@/components/ui/spinner";
import api from "@/lib/api-client";
import { formatFechaEs } from "@/lib/utils";
import { useAuth } from "@/lib/auth";
import { toast } from "sonner";
import { FileEdit, Eye, Send, ArrowLeft, ArrowRight, Loader2 } from "lucide-react";

interface Catalogo {
  id: number; nombre: string;
}
interface Plantilla { id: number; plataforma_id: number | null; tipo_comunicado_id: number; asunto: string; html: string; }
interface ReglaResult { entidad_afectada: string; asunto_template: string; descripcion_template: string; entidad_formateada?: string; }

const hoy = () => new Date();
const toDateInput = (d: Date) => d.toISOString().split("T")[0];
const toTimeInput = (d: Date) => `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;

function renderTemplate(html: string, vars: Record<string, string>): string {
  let result = html;
  for (const [key, val] of Object.entries(vars)) {
    result = result.replace(new RegExp(`\\{\\{\\s*${key}\\s*\\}\\}`, "g"), val || "");
  }
  return result;
}

export default function NuevaNovedadPage() {
  const [catalogos, setCatalogos] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [step, setStep] = useState(1);
  const [terceros, setTerceros] = useState<Catalogo[]>([]);
  const [correosBD, setCorreosBD] = useState<string[]>([]);
  const [plantillasFiltradas, setPlantillasFiltradas] = useState<Plantilla[]>([]);
  const [regla, setRegla] = useState<ReglaResult | null>(null);
  const [consecutivoPreview, setConsecutivoPreview] = useState("");
  const [previewHtml, setPreviewHtml] = useState("");
  const [templateArgsCache, setTemplateArgsCache] = useState<Record<string, string>>({});
  const [fechaInicio, setFechaInicio] = useState(toDateInput(hoy()));
  const [horaInicio, setHoraInicio] = useState(toTimeInput(hoy()));
  const [form, setForm] = useState({
    plataforma_id: "", servicio_id: "", tipo_id: "", tercero_id: "",
    analista_id: "", afectacion: "Afecta Disponibilidad",
    asunto: "", descripcion: "", correos: "", diagnostico: "",
    requiere_aprobacion: false, es_externa: true, plantilla_id: ""
  });
  const { tienePermiso, serviciosRestringidos } = useAuth();
  const esAdmin = tienePermiso("ver_admin");

  const serviciosPermitidos = useCallback(() => {
    const todos = catalogos?.servicios || [];
    if (!serviciosRestringidos || serviciosRestringidos.length === 0) return todos;
    return todos.filter((s: any) => serviciosRestringidos.includes(s.id));
  }, [catalogos, serviciosRestringidos]);

  useEffect(() => {
    Promise.all([
      api.get<any>("/comunicados/catalogos"),
      api.get<any>("/comunicados/correos-internos-cc")
    ]).then(([cat, cc]) => {
      setCatalogos(cat);
      const userInfo = JSON.parse(localStorage.getItem("user_info") || "{}");
      const match = (cat.analistas || []).find((a: any) => a.correo === userInfo.correo);
      if (match) setForm(f => ({ ...f, analista_id: String(match.id) }));
    }).catch(console.error).finally(() => setLoading(false));
  }, []);

  const sel = (key: string) => {
    const v = (form as any)[key];
    if (!catalogos) return "";
    const m: Record<string, string> = {
      plataforma_id: "plataformas", servicio_id: "servicios",
      tipo_id: "tipos", analista_id: "analistas"
    };
    const arr = catalogos[m[key]] || [];
    return arr.find((x: any) => String(x.id) === v)?.nombre || v;
  };

  const loadTerceros = useCallback(async (servicioId: string) => {
    if (!servicioId) { setTerceros([]); return; }
    const data = await api.get<Catalogo[]>(`/comunicados/terceros-por-servicio/${servicioId}`);
    setTerceros(data);
  }, []);

  const loadCorreos = useCallback(async () => {
    const sId = form.servicio_id, pId = form.plataforma_id;
    if (!sId || !pId) return;
    const sName = sel("servicio_id"), pName = sel("plataforma_id");
    const data = await api.get<string[]>(`/comunicados/correos-segmentados?servicio_id=${sId}&plataforma_id=${pId}&nombre_servicio=${encodeURIComponent(sName)}&nombre_plataforma=${encodeURIComponent(pName)}`);
    setCorreosBD(data);
    if (data.length) setForm(f => ({ ...f, correos: data.join(", ") }));
  }, [form.servicio_id, form.plataforma_id]);

  const loadConsecutivo = useCallback(async () => {
    if (!form.tipo_id || !catalogos?.tipos) return;
    const tipo = catalogos.tipos.find((t: any) => String(t.id) === form.tipo_id);
    if (!tipo?.serie_id) return;
    const data = await api.get<any>(`/comunicados/siguiente-consecutivo/${tipo.serie_id}`);
    setConsecutivoPreview(data.preview || `${data.codigo}-${data.siguiente_valor}`);
  }, [form.tipo_id, catalogos]);

  const loadRegla = useCallback(async (fase: string) => {
    if (!form.plataforma_id || !form.servicio_id || !form.tipo_id) return;
    if (!consecutivoPreview) await loadConsecutivo();
    const pId = Number(form.plataforma_id), sId = Number(form.servicio_id);
    const tId = Number(form.tipo_id), tercId = form.tercero_id ? Number(form.tercero_id) : null;

    const plat = catalogos?.plataformas?.find((x: any) => x.id === pId);
    const serv = catalogos?.servicios?.find((x: any) => x.id === sId);
    const terc = terceros.find((x: any) => x.id === tercId);
    const fmtKwargs = {
      consecutivo: consecutivoPreview || "PREV-000",
      plataforma: plat?.nombre || "", servicio: serv?.nombre || "", tercero: terc?.nombre || ""
    };

    const evalBody = { plat_id: pId, serv_id: sId, tipo_id: tId, fase, terc_id: tercId, kwargs: fmtKwargs };
    const reglaData = await api.post<any>("/comunicados/reglas-preview", evalBody);
    setRegla(reglaData);
    const entidad = reglaData.entidad_formateada || fmtKwargs.tercero;
    const asuntoCalc = (reglaData.asunto_template || "{consecutivo} - Comunicado sobre {servicio}")
      .replace("{consecutivo}", consecutivoPreview || "PREV-000")
      .replace("{plataforma}", plat?.nombre || "")
      .replace("{servicio}", serv?.nombre || "")
      .replace("{tercero}", terc?.nombre || "")
      .replace("{entidad}", entidad);
    const descCalc = (reglaData.descripcion_template || "Notificación del servicio {servicio} para {entidad}.")
      .replace("{consecutivo}", consecutivoPreview || "PREV-000")
      .replace("{plataforma}", plat?.nombre || "")
      .replace("{servicio}", serv?.nombre || "")
      .replace("{tercero}", terc?.nombre || "")
      .replace("{entidad}", entidad);
    setForm(f => ({ ...f, asunto: asuntoCalc, descripcion: descCalc }));
  }, [form.plataforma_id, form.servicio_id, form.tipo_id, form.tercero_id, consecutivoPreview, terceros, catalogos]);

  const filterPlantillas = useCallback(async () => {
    if (!form.tipo_id || !catalogos?.plantillas) return;
    const searchKw = ["base", "novedad", "apertura", "incidente"];
    const data = await api.get<Plantilla[]>(`/comunicados/plantillas-por-tipo?tipo_comunicado_id=${form.tipo_id}&plataforma_id=${form.plataforma_id || ""}&keyword=${searchKw.join(",")}`);
    const filtradas = data.length ? data : catalogos.plantillas.filter((p: any) => String(p.tipo_comunicado_id) === form.tipo_id);
    setPlantillasFiltradas(filtradas);
    if (filtradas.length >= 1) setForm(f => ({ ...f, plantilla_id: String(filtradas[0].id) }));
  }, [form.tipo_id, form.plataforma_id, catalogos]);

  const generarPreview = async () => {
    if (!form.servicio_id || !form.plataforma_id) { toast.error("Selecciona plataforma y servicio"); return; }

    let plantillaId = form.plantilla_id;
    if (!plantillaId && plantillasFiltradas.length > 0) {
      plantillaId = String(plantillasFiltradas[0].id);
      setForm(f => ({ ...f, plantilla_id: plantillaId }));
    }
    if (!plantillaId) { toast.error("No hay plantillas disponibles"); return; }

    const inicioDt = new Date(`${fechaInicio}T${horaInicio}`);
    if (inicioDt > new Date()) { toast.error("La fecha/hora de inicio no puede ser futura"); return; }

    setSubmitting(true);
    try {
      const plat = catalogos?.plataformas?.find((x: any) => x.id === Number(form.plataforma_id));
      const serv = catalogos?.servicios?.find((x: any) => x.id === Number(form.servicio_id));
      const terc = terceros.find((x: any) => x.id === Number(form.tercero_id));
      const plant = plantillasFiltradas.find((x: any) => String(x.id) === plantillaId);
      if (!plant) { toast.error("Plantilla no encontrada"); return; }

      const servicioStr = plat?.nombre === "GENERAL" ? (regla?.entidad_formateada || "") : `${serv?.nombre || ""}${terc ? " - " + terc.nombre : ""}`;
      const tiempoNovedad = Math.floor((new Date().getTime() - inicioDt.getTime()) / 1000);
      const tiempoStr = tiempoNovedad >= 3600
        ? `${Math.floor(tiempoNovedad / 3600)}h ${Math.floor((tiempoNovedad % 3600) / 60)}m`
        : `${Math.floor(tiempoNovedad / 60)}m`;

      const templateArgs = {
        consecutivo: consecutivoPreview,
        servicio: servicioStr,
        descripcion: form.descripcion || "Sin descripción",
        cliente: regla?.entidad_formateada || terc?.nombre || "",
        fecha_comunicado: formatFechaEs(new Date()),
        fecha_inicio: formatFechaEs(inicioDt),
        tiempo_novedad: tiempoStr,
        afectacion: form.afectacion,
      };
      setTemplateArgsCache(templateArgs);

      const html = renderTemplate(plant.html, templateArgs);
      setPreviewHtml(html);
      setStep(3);
    } catch (e: any) {
      toast.error(e.message || "Error generando preview");
    } finally {
      setSubmitting(false);
    }
  };

  const confirmarEnvio = async () => {
    setSubmitting(true);
    try {
      const plat = catalogos?.plataformas?.find((x: any) => x.id === Number(form.plataforma_id));
      const serv = catalogos?.servicios?.find((x: any) => x.id === Number(form.servicio_id));
      const tipo = catalogos?.tipos?.find((x: any) => x.id === Number(form.tipo_id));
      const inicioDt = new Date(`${fechaInicio}T${horaInicio}`);

      const db_data: Record<string, any> = {
        plataforma_id: Number(form.plataforma_id), servicio_id: Number(form.servicio_id),
        tipo_comunicado_id: Number(form.tipo_id), serie_id: tipo?.serie_id || 1,
        analista_id: Number(form.analista_id), tercero_id: form.tercero_id ? Number(form.tercero_id) : null,
        afectacion: form.afectacion, asunto_ui: form.asunto,
        consecutivo_preview: consecutivoPreview, descripcion: form.descripcion,
        diagnostico_falla: form.diagnostico, correos_input: form.correos,
        es_externa: form.es_externa, requiere_aprobacion: form.requiere_aprobacion,
        fecha_creacion: inicioDt.toISOString()
      };

      const plant = plantillasFiltradas.find((x: any) => String(x.id) === form.plantilla_id);
      const preview = { template_html: plant?.html || "", template_args: templateArgsCache };

      await api.post("/comunicados/apertura", { db_data, preview });
      toast.success("Novedad registrada exitosamente");
      setStep(1); setPreviewHtml(""); setTemplateArgsCache({});
      setForm(f => ({ ...f, asunto: "", descripcion: "", correos: "", diagnostico: "" }));
      const cc = await api.get<any>("/comunicados/correos-internos-cc");
    } catch (e: any) {
      toast.error(e.message || "Error al enviar");
    } finally {
      setSubmitting(false);
    }
  };

  const handleFieldChange = (field: string, value: any) => {
    setForm(f => ({ ...f, [field]: value }));
    if (field === "servicio_id") { loadTerceros(value); }
    if (field === "servicio_id" || field === "plataforma_id") {
      if (form.servicio_id && value) setTimeout(loadCorreos, 100);
    }
    if (field === "tipo_id") {
      if (value && catalogos?.tipos) {
        const tipo = catalogos.tipos.find((t: any) => String(t.id) === value);
        if (tipo?.serie_id) {
          api.get<any>(`/comunicados/siguiente-consecutivo/${tipo.serie_id}`)
            .then(d => setConsecutivoPreview(d.preview || `${d.codigo}-${d.siguiente_valor}`))
            .catch(console.error);
        }
      }
    }
  };

  if (loading) return <AppShell><PageLoader /></AppShell>;

  return (
    <AppShell>
      <div className="max-w-4xl mx-auto animate-fade-in space-y-6">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-primary-light">
            <FileEdit className="text-primary" size={24} />
          </div>
          <div>
            <h1 className="text-2xl font-extrabold text-accent">Apertura de Novedad</h1>
            <p className="text-sm text-muted-foreground">Asistente para creación de comunicados</p>
          </div>
        </div>

        <div className="flex items-center gap-2 mb-6">
          {["Clasificación", "Detalles", "Previsualización"].map((label, i) => (
            <div key={label} className="flex items-center gap-2 flex-1">
              <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold transition-colors ${
                i + 1 <= step ? "bg-primary text-white" : "bg-muted text-muted-foreground"
              }`}>{i + 1}</div>
              <span className={`text-xs font-medium ${i + 1 <= step ? "text-accent" : "text-muted-foreground"}`}>{label}</span>
              {i < 2 && <div className="flex-1 h-px bg-border" />}
            </div>
          ))}
        </div>

        {step === 1 && (
          <Card>
            <CardContent className="p-6 space-y-4">
              <h3 className="font-bold text-accent">1. Clasificación del Incidente</h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <FieldSelect label="Plataforma" value={form.plataforma_id} onChange={v => handleFieldChange("plataforma_id", v)}
                  options={catalogos?.plataformas?.map((p: any) => ({ value: String(p.id), label: p.nombre })) || []} />
                <FieldSelect label="Servicio Afectado" value={form.servicio_id} onChange={v => handleFieldChange("servicio_id", v)}
                  options={serviciosPermitidos().map((s: any) => ({ value: String(s.id), label: s.nombre }))} />
                <FieldSelect label="Tercero / Aliado" value={form.tercero_id} onChange={v => handleFieldChange("tercero_id", v)}
                  options={terceros.map((t: any) => ({ value: String(t.id), label: t.nombre }))} placeholder="N/A" />
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <FieldSelect label="Tipo Comunicado" value={form.tipo_id} onChange={v => handleFieldChange("tipo_id", v)}
                  options={catalogos?.tipos?.filter((t: any) => t.nombre !== "Mantenimiento").map((t: any) => ({ value: String(t.id), label: t.nombre })) || []} />
                <FieldSelect label="Analista" value={form.analista_id} onChange={v => handleFieldChange("analista_id", v)}
                  options={catalogos?.analistas?.map((a: any) => ({ value: String(a.id), label: `${a.nombre} ${a.apellido}` })) || []}
                  disabled={!esAdmin} />
                <FieldSelect label="Afectación" value={form.afectacion} onChange={v => handleFieldChange("afectacion", v)}
                  options={[
                    { value: "Afecta Disponibilidad", label: "Afecta Disponibilidad" },
                    { value: "Afectación Parcial", label: "Afectación Parcial" },
                    { value: "No Afecta", label: "No Afecta" }
                  ]} />
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
                <div className="space-y-2">
                  <label className="text-sm font-semibold">Fecha Inicio Novedad</label>
                  <Input type="date" value={fechaInicio} onChange={e => setFechaInicio(e.target.value)} />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-semibold">Hora Inicio Novedad</label>
                  <Input type="time" value={horaInicio} onChange={e => setHoraInicio(e.target.value)} />
                </div>
              </div>
              <div className="flex justify-end pt-4">
                <Button onClick={async () => {
                  if (!consecutivoPreview) await loadConsecutivo();
                  filterPlantillas();
                  loadRegla("APERTURA");
                  setStep(2);
                }} className="gap-2">
                  Siguiente <ArrowRight size={16} />
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {step === 2 && (
          <Card>
            <CardContent className="p-6 space-y-4">
              <h3 className="font-bold text-accent">2. Detalles y Generación</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <label className="text-sm font-semibold">Consecutivo</label>
                  <Input value={consecutivoPreview} disabled />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-semibold">Asunto Final</label>
                  <Input value={form.asunto} onChange={e => setForm(f => ({ ...f, asunto: e.target.value }))} />
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <label className="text-sm font-semibold">Destinatarios</label>
                  <Textarea value={form.correos} onChange={e => setForm(f => ({ ...f, correos: e.target.value }))} rows={3}
                    placeholder="correo1@empresa.com, correo2@empresa.com" />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-semibold">Plantilla</label>
                  <select className="w-full h-10 rounded-xl border border-input bg-background px-3 text-sm"
                    value={form.plantilla_id} onChange={e => setForm(f => ({ ...f, plantilla_id: e.target.value }))}>
                    <option value="">Seleccionar plantilla...</option>
                    {plantillasFiltradas.map((p: Plantilla) => (
                      <option key={p.id} value={String(p.id)}>{p.asunto}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-semibold">Descripción Pública</label>
                <Textarea value={form.descripcion} onChange={e => setForm(f => ({ ...f, descripcion: e.target.value }))} rows={4} />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-semibold">Diagnóstico Técnico (Interno)</label>
                <Textarea value={form.diagnostico} onChange={e => setForm(f => ({ ...f, diagnostico: e.target.value }))} rows={3} />
              </div>

              <div className="flex items-center gap-6 pt-2">
                <label className="flex items-center gap-2 text-sm cursor-pointer">
                  <input type="checkbox" checked={form.requiere_aprobacion}
                    onChange={e => setForm(f => ({ ...f, requiere_aprobacion: e.target.checked }))}
                    className="rounded border-gray-300 w-4 h-4" />
                  Requiere aprobación
                </label>
                <label className="flex items-center gap-2 text-sm cursor-pointer">
                  <input type="checkbox" checked={form.es_externa}
                    onChange={e => setForm(f => ({ ...f, es_externa: e.target.checked }))}
                    className="rounded border-gray-300 w-4 h-4" />
                  Comunicación externa
                </label>
              </div>

              <div className="flex justify-between pt-4">
                <Button variant="outline" onClick={() => setStep(1)} className="gap-2"><ArrowLeft size={16} /> Atrás</Button>
                <Button onClick={generarPreview} disabled={submitting} className="gap-2">
                  {submitting ? <Loader2 size={16} className="animate-spin" /> : <Eye size={16} />}
                  Vista Previa
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {step === 3 && (
          <Card>
            <CardContent className="p-6 space-y-4">
              <h3 className="font-bold text-accent">3. Vista Previa y Confirmación</h3>
              <div className="flex items-center gap-2 mb-2">
                <Badge variant="warning">Pendiente de Acción</Badge>
                <span className="text-xs text-muted-foreground">Verifica el contenido antes de enviar</span>
              </div>
              {previewHtml && (
                <div className="rounded-xl border bg-white overflow-hidden" style={{ height: 500 }}>
                  <iframe srcDoc={previewHtml} width="100%" height="100%" style={{ border: "none" }} title="Preview" />
                </div>
              )}
              <div className="flex justify-between pt-4">
                <Button variant="outline" onClick={() => setStep(2)} className="gap-2"><ArrowLeft size={16} /> Editar</Button>
                <Button onClick={confirmarEnvio} disabled={submitting} className="gap-2">
                  {submitting ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
                  {submitting ? "Enviando..." : "Confirmar y Enviar"}
                </Button>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </AppShell>
  );
}

function FieldSelect({ label, value, onChange, options, placeholder, disabled }: {
  label: string; value: string; onChange: (v: string) => void;
  options: { value: string; label: string }[]; placeholder?: string; disabled?: boolean;
}) {
  return (
    <div className="space-y-2">
      <label className="text-sm font-semibold">{label}</label>
      <select className="w-full h-10 rounded-xl border border-input bg-background px-3 text-sm disabled:opacity-60 disabled:cursor-not-allowed"
        value={value} onChange={e => onChange(e.target.value)} disabled={disabled}>
        <option value="">{placeholder || "Seleccionar..."}</option>
        {options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </div>
  );
}
