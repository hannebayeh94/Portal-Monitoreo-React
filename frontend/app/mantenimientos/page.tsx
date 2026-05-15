"use client";

import { useState, useEffect, useCallback } from "react";
import { AppShell } from "@/components/layout/app-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { PageLoader, EmptyState } from "@/components/ui/spinner";
import { DataTable } from "@/components/shared/data-table";
import api from "@/lib/api-client";
import { formatFechaEs } from "@/lib/utils";
import { useAuth } from "@/lib/auth";
import { toast } from "sonner";
import { Wrench, Calendar, CheckCircle, Send, Loader2, Eye, ArrowLeft, ArrowRight, XCircle } from "lucide-react";

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

function calcDuracionStr(inicio: Date, fin: Date): string {
  const seg = Math.floor((fin.getTime() - inicio.getTime()) / 1000);
  if (seg < 0) return "0m";
  const h = Math.floor(seg / 3600);
  const m = Math.floor((seg % 3600) / 60);
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

export default function MantenimientosPage() {
  const [modo, setModo] = useState<"programar" | "finalizar">("programar");
  const [catalogos, setCatalogos] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [form, setForm] = useState({
    plataforma_id: "", servicio_id: "", tipo_id: "", analista_id: "",
    tercero_id: "", afectacion: "No Afecta",
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
  const [terceros, setTerceros] = useState<any[]>([]);
  const [correosBD, setCorreosBD] = useState<string[]>([]);
  const [plantillasFiltradas, setPlantillasFiltradas] = useState<any[]>([]);
  const [regla, setRegla] = useState<any>(null);
  const [consecutivoPreview, setConsecutivoPreview] = useState("");
  const [previewHtml, setPreviewHtml] = useState("");
  const [templateArgsCache, setTemplateArgsCache] = useState<Record<string, string>>({});
  const [step, setStep] = useState(1);
  const [abiertos, setAbiertos] = useState<any[]>([]);
  const [selectedMantenimiento, setSelectedMantenimiento] = useState<any>(null);
  const [cierreForm, setCierreForm] = useState({ solucion: "", asunto_cierre: "", correos_finales: "" });
  const [cierrePreviewHtml, setCierrePreviewHtml] = useState("");
  const [fechaInicio, setFechaInicio] = useState(toDateInput(hoy()));
  const [horaInicio, setHoraInicio] = useState(toTimeInput(hoy()));
  const [fechaFin, setFechaFin] = useState(toDateInput(hoy()));
  const [horaFin, setHoraFin] = useState(toTimeInput(new Date(Date.now() + 2 * 3600000)));
  const [fechaCierreMant, setFechaCierreMant] = useState(toDateInput(hoy()));
  const [horaCierreMant, setHoraCierreMant] = useState(toTimeInput(hoy()));
  const [cierreStep, setCierreStep] = useState(1);
  const [plantillasCierre, setPlantillasCierre] = useState<any[]>([]);
  const [plantillaCierreId, setPlantillaCierreId] = useState("");

  useEffect(() => {
    Promise.all([
      api.get<any>("/comunicados/catalogos"),
      api.get<any[]>("/comunicados/abiertos?tipo=mantenimiento"),
      api.get<any>("/comunicados/correos-internos-cc")
    ]).then(([cat, abiertosData, cc]) => {
      setCatalogos(cat);
      setAbiertos(abiertosData);
      const user = JSON.parse(localStorage.getItem("user_info") || "{}");
      const match = (cat.analistas || []).find((a: any) => a.correo === user.correo);
      if (match) setForm(f => ({ ...f, analista_id: String(match.id) }));
      const tipoManto = (cat.tipos || []).find((t: any) => t.nombre?.toLowerCase().includes("mantenimiento"));
      if (tipoManto) setForm(f => ({ ...f, tipo_id: String(tipoManto.id) }));
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
    const data = await api.get<any[]>(`/comunicados/terceros-por-servicio/${servicioId}`);
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
    const pId = Number(form.plataforma_id), sId = Number(form.servicio_id);
    const tId = Number(form.tipo_id), tercId = form.tercero_id ? Number(form.tercero_id) : null;
    const plat = catalogos?.plataformas?.find((x: any) => x.id === pId);
    const serv = catalogos?.servicios?.find((x: any) => x.id === sId);
    const terc = terceros.find((x: any) => x.id === tercId);
    const fmtKwargs = {
      consecutivo: consecutivoPreview || "MTTO-000",
      plataforma: plat?.nombre || "", servicio: serv?.nombre || "", tercero: terc?.nombre || ""
    };
    const evalBody = { plat_id: pId, serv_id: sId, tipo_id: tId, fase, terc_id: tercId, kwargs: fmtKwargs };
    const reglaData = await api.post<any>("/comunicados/reglas-preview", evalBody);
    setRegla(reglaData);
    const entidad = reglaData.entidad_formateada || fmtKwargs.tercero;
    const asuntoCalc = (reglaData.asunto_template || "{consecutivo} - Mantenimiento - {servicio}")
      .replace("{consecutivo}", consecutivoPreview || "MTTO-000")
      .replace("{plataforma}", plat?.nombre || "")
      .replace("{servicio}", serv?.nombre || "")
      .replace("{tercero}", terc?.nombre || "")
      .replace("{entidad}", entidad);
    const descCalc = (reglaData.descripcion_template || "Ventana de mantenimiento para {servicio}.")
      .replace("{consecutivo}", consecutivoPreview || "MTTO-000")
      .replace("{plataforma}", plat?.nombre || "")
      .replace("{servicio}", serv?.nombre || "")
      .replace("{tercero}", terc?.nombre || "")
      .replace("{entidad}", entidad);
    setForm(f => ({ ...f, asunto: asuntoCalc, descripcion: descCalc }));
  }, [form.plataforma_id, form.servicio_id, form.tipo_id, form.tercero_id, consecutivoPreview, terceros, catalogos]);

  const filterPlantillas = useCallback(async () => {
    if (!form.tipo_id || !catalogos?.plantillas) return;
    const searchKw = ["mantenimiento"];
    const data = await api.get<any[]>(`/comunicados/plantillas-por-tipo?tipo_comunicado_id=${form.tipo_id}&plataforma_id=${form.plataforma_id || ""}&keyword=${searchKw.join(",")}`);
    const filtradas = data.length ? data : catalogos.plantillas.filter((p: any) => String(p.tipo_comunicado_id) === form.tipo_id);
    setPlantillasFiltradas(filtradas);
    if (filtradas.length >= 1) setForm(f => ({ ...f, plantilla_id: String(filtradas[0].id) }));
  }, [form.tipo_id, form.plataforma_id, catalogos]);

  const irAPaso2 = async () => {
    if (!form.plataforma_id || !form.servicio_id) {
      toast.error("Selecciona plataforma y servicio");
      return;
    }
    const inicioDt = new Date(`${fechaInicio}T${horaInicio}`);
    const finDt = new Date(`${fechaFin}T${horaFin}`);
    if (finDt <= inicioDt) {
      toast.error("La fecha/hora de fin debe ser posterior a la fecha de inicio");
      return;
    }
    if (!consecutivoPreview) await loadConsecutivo();
    await Promise.all([filterPlantillas(), loadRegla("MANTENIMIENTO")]);
    setStep(2);
  };

  const generarPreview = async () => {
    let plantillaId = form.plantilla_id;
    if (!plantillaId && plantillasFiltradas.length > 0) {
      plantillaId = String(plantillasFiltradas[0].id);
      setForm(f => ({ ...f, plantilla_id: plantillaId }));
    }
    if (!plantillaId) { toast.error("No hay plantillas disponibles"); return; }
    setSubmitting(true);
    try {
      const plat = catalogos?.plataformas?.find((x: any) => x.id === Number(form.plataforma_id));
      const serv = catalogos?.servicios?.find((x: any) => x.id === Number(form.servicio_id));
      const plant = plantillasFiltradas.find((x: any) => String(x.id) === plantillaId);
      if (!plant) { toast.error("Plantilla no encontrada"); return; }

      const inicioDt = new Date(`${fechaInicio}T${horaInicio}`);
      const finDt = new Date(`${fechaFin}T${horaFin}`);
      const servicioStr = `${serv?.nombre || ""}`;

      const templateArgs = {
        consecutivo: consecutivoPreview,
        servicio: servicioStr,
        descripcion: form.descripcion || "Sin descripción",
        cliente: regla?.entidad_formateada || "",
        fecha_comunicado: formatFechaEs(new Date()),
        fecha_inicio: formatFechaEs(inicioDt),
        fecha_fin: formatFechaEs(finDt),
        tiempo_estimado: calcDuracionStr(inicioDt, finDt),
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

  const confirmarApertura = async () => {
    setSubmitting(true);
    try {
      const tipo = catalogos?.tipos?.find((x: any) => String(x.id) === form.tipo_id);
      const inicioDt = new Date(`${fechaInicio}T${horaInicio}`);
      const finDt = new Date(`${fechaFin}T${horaFin}`);
      const descFinal = `${form.descripcion}\n\n[Ventana Programada: ${formatFechaEs(inicioDt)} hasta ${formatFechaEs(finDt)} - Duración: ${calcDuracionStr(inicioDt, finDt)}]`;

      const db_data: Record<string, any> = {
        plataforma_id: Number(form.plataforma_id), servicio_id: Number(form.servicio_id),
        tipo_comunicado_id: Number(form.tipo_id), serie_id: tipo?.serie_id || 1,
        analista_id: Number(form.analista_id), tercero_id: form.tercero_id ? Number(form.tercero_id) : null,
        afectacion: form.afectacion, asunto_ui: form.asunto,
        consecutivo_preview: consecutivoPreview, descripcion: descFinal,
        diagnostico_falla: form.diagnostico, correos_input: form.correos,
        es_externa: form.es_externa, requiere_aprobacion: form.requiere_aprobacion,
        fecha_creacion: inicioDt.toISOString()
      };

      const plant = plantillasFiltradas.find((x: any) => String(x.id) === form.plantilla_id);
      const preview = { template_html: plant?.html || "", template_args: templateArgsCache };

      await api.post("/comunicados/apertura", { db_data, preview });
      toast.success("Ventana de mantenimiento creada exitosamente");
      setStep(1); setPreviewHtml(""); setTemplateArgsCache({});
      setForm(f => ({ ...f, asunto: "", descripcion: "", correos: "", diagnostico: "" }));
      const refreshed = await api.get<any[]>("/comunicados/abiertos?tipo=mantenimiento");
      setAbiertos(refreshed);
    } catch (e: any) {
      toast.error(e.message || "Error al crear mantenimiento");
    } finally {
      setSubmitting(false);
    }
  };

  const handleFieldChange = (field: string, value: any) => {
    setForm(f => ({ ...f, [field]: value }));
    if (field === "servicio_id") loadTerceros(value);
    if (field === "servicio_id" || field === "plataforma_id") {
      if (form.servicio_id && value) setTimeout(loadCorreos, 100);
    }
    if (field === "tipo_id" && value && catalogos?.tipos) {
      const tipo = catalogos.tipos.find((t: any) => String(t.id) === value);
      if (tipo?.serie_id) {
        api.get<any>(`/comunicados/siguiente-consecutivo/${tipo.serie_id}`)
          .then(d => setConsecutivoPreview(d.preview || `${d.codigo}-${d.siguiente_valor}`))
          .catch(console.error);
      }
    }
  };

  const seleccionarMantenimiento = async (item: any) => {
    setSelectedMantenimiento(item);
    setCierreStep(1);
    setPlantillaCierreId("");
    setCierrePreviewHtml("");
    setFechaCierreMant(toDateInput(hoy()));
    setHoraCierreMant(toTimeInput(hoy()));
    const asuntoCierre = `[SOLUCIONADO] ${item.asunto_final || item.consecutivo_num}`;
    setCierreForm({
      solucion: "",
      asunto_cierre: asuntoCierre,
      correos_finales: item.emails_apertura || ""
    });

    const plantillas = (catalogos?.plantillas || []).filter((p: any) => {
      if (p.tipo_comunicado_id !== item.tipo_comunicado_id) return false;
      if (item.plataforma_id && p.plataforma_id && p.plataforma_id !== item.plataforma_id) return false;
      return true;
    });
    const kw_fin = ["fin", "cierre", "restablecimiento", "solucion"];
    const filtradas = plantillas.filter((p: any) =>
      kw_fin.some(kw => p.asunto.toLowerCase().replace(/\s/g, "").includes(kw))
    );
    const cierreFinal = filtradas.length > 0 ? filtradas : plantillas;
    setPlantillasCierre(cierreFinal);
    if (cierreFinal.length >= 1) setPlantillaCierreId(String(cierreFinal[0].id));
  };

  const irAPreviewCierre = () => {
    let pid = plantillaCierreId;
    if (!pid && plantillasCierre.length > 0) {
      pid = String(plantillasCierre[0].id);
      setPlantillaCierreId(pid);
    }
    if (!pid) { toast.error("No hay plantillas de cierre disponibles"); return; }
    if (!selectedMantenimiento) return;

    const cierreDt = new Date(`${fechaCierreMant}T${horaCierreMant}`);
    if (cierreDt < new Date(selectedMantenimiento.fecha_creacion)) {
      toast.error("La fecha/hora de cierre no puede ser anterior a la creación"); return;
    }
    if (cierreDt > new Date()) {
      toast.error("La fecha/hora de cierre no puede ser futura"); return;
    }

    const segundos = Math.floor((cierreDt.getTime() - new Date(selectedMantenimiento.fecha_creacion).getTime()) / 1000);
    const tiempoStr = segundos >= 3600
      ? `${Math.floor(segundos / 3600)}h ${Math.floor((segundos % 3600) / 60)}m`
      : `${Math.floor(segundos / 60)}m`;

    const plant = plantillasCierre.find((p: any) => String(p.id) === plantillaCierreId);
    const templateArgs = {
      consecutivo: selectedMantenimiento.consecutivo_num,
      servicio: selectedMantenimiento.servicio_nom || "",
      descripcion_novedad: selectedMantenimiento.descripcion || "",
      descripcion_cierre: `Se finaliza la ventana de mantenimiento ${selectedMantenimiento.consecutivo_num}.`,
      cliente: selectedMantenimiento.tercero_nom || "",
      fecha_comunicado: formatFechaEs(new Date()),
      fecha_inicio: formatFechaEs(new Date(selectedMantenimiento.fecha_creacion)),
      fecha_cierre: formatFechaEs(cierreDt),
      tiempo_transcurrido: tiempoStr,
    };

    const html = renderTemplate(plant?.html || "", templateArgs);
    setCierrePreviewHtml(html);
    setCierreStep(2);
  };

  const confirmarCierre = async () => {
    if (!selectedMantenimiento) { toast.error("Selecciona una ventana activa"); return; }
    const cierreDt = new Date(`${fechaCierreMant}T${horaCierreMant}`);
    if (cierreDt < new Date(selectedMantenimiento.fecha_creacion)) {
      toast.error("La fecha/hora de cierre no puede ser anterior a la creación");
      return;
    }
    if (cierreDt > new Date()) {
      toast.error("La fecha/hora de cierre no puede ser futura");
      return;
    }
    setSubmitting(true);
    try {
      await loadRegla("FIN_MANTENIMIENTO");
      const asuntoNorm = `[SOLUCIONADO] ${selectedMantenimiento.asunto_final || selectedMantenimiento.consecutivo_num}`;
      await api.post(`/comunicados/cierre/${selectedMantenimiento.id}`, {
        solucion_interna: cierreForm.solucion,
        fecha_hora_cierre: cierreDt.toISOString(),
        html: cierrePreviewHtml,
        asunto_norm: asuntoNorm,
        correos_finales: cierreForm.correos_finales,
        requiere_aprobacion: selectedMantenimiento.requiere_aprobacion || false
      });
      toast.success("Mantenimiento finalizado exitosamente");
      setSelectedMantenimiento(null);
      setCierreForm({ solucion: "", asunto_cierre: "", correos_finales: "" });
      setCierrePreviewHtml("");
      const refreshed = await api.get<any[]>("/comunicados/abiertos?tipo=mantenimiento");
      setAbiertos(refreshed);
    } catch (e: any) {
      toast.error(e.message || "Error al finalizar mantenimiento");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return <AppShell><PageLoader /></AppShell>;

  return (
    <AppShell>
      <div className="max-w-5xl mx-auto animate-fade-in space-y-6">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-primary-light"><Wrench className="text-primary" size={24} /></div>
          <div><h1 className="text-2xl font-extrabold text-accent">Gestión de Mantenimientos</h1>
          <p className="text-sm text-muted-foreground">Programa y finaliza ventanas de mantenimiento</p></div>
        </div>

        <div className="flex gap-2 p-1 rounded-xl bg-muted w-fit">
          <button onClick={() => { setModo("programar"); setStep(1); }} className={"px-4 py-2 rounded-lg text-sm font-medium transition-all " + (modo === "programar" ? "bg-white text-accent shadow-sm" : "text-muted-foreground hover:text-accent")}><Calendar size={16} className="inline mr-1.5" /> Programar</button>
          <button onClick={() => setModo("finalizar")} className={"px-4 py-2 rounded-lg text-sm font-medium transition-all " + (modo === "finalizar" ? "bg-white text-accent shadow-sm" : "text-muted-foreground hover:text-accent")}><CheckCircle size={16} className="inline mr-1.5" /> Finalizar</button>
        </div>

        {modo === "programar" ? (
          <>
            <div className="flex items-center gap-2 mb-4">
              {["Clasificación", "Detalles", "Confirmación"].map((label, i) => (
                <div key={label} className="flex items-center gap-2 flex-1">
                  <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold transition-colors ${i + 1 <= step ? "bg-primary text-white" : "bg-muted text-muted-foreground"}`}>{i + 1}</div>
                  <span className={`text-xs font-medium ${i + 1 <= step ? "text-accent" : "text-muted-foreground"}`}>{label}</span>
                  {i < 2 && <div className="flex-1 h-px bg-border" />}
                </div>
              ))}
            </div>

            {step === 1 && (
              <Card><CardContent className="p-6 space-y-4">
                <h3 className="font-bold text-accent">1. Clasificación del Mantenimiento</h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <FieldSelect label="Plataforma" value={form.plataforma_id} onChange={v => handleFieldChange("plataforma_id", v)}
                    options={catalogos?.plataformas?.map((p: any) => ({ value: String(p.id), label: p.nombre })) || []} />
                  <FieldSelect label="Servicio" value={form.servicio_id} onChange={v => handleFieldChange("servicio_id", v)}
                    options={serviciosPermitidos().map((s: any) => ({ value: String(s.id), label: s.nombre }))} />
                  <FieldSelect label="Tercero" value={form.tercero_id} onChange={v => handleFieldChange("tercero_id", v)}
                    options={terceros.map((t: any) => ({ value: String(t.id), label: t.nombre }))} placeholder="N/A" />
                </div>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <FieldSelect label="Tipo Comunicado" value={form.tipo_id} onChange={v => handleFieldChange("tipo_id", v)}
                    options={catalogos?.tipos?.filter((t: any) => t.nombre?.toLowerCase().includes("mantenimiento")).map((t: any) => ({ value: String(t.id), label: t.nombre })) || []} />
                  <FieldSelect label="Analista" value={form.analista_id} onChange={v => handleFieldChange("analista_id", v)}
                    options={catalogos?.analistas?.map((a: any) => ({ value: String(a.id), label: `${a.nombre} ${a.apellido}` })) || []}
                    disabled={!esAdmin} />
                  <FieldSelect label="Afectación" value={form.afectacion} onChange={v => handleFieldChange("afectacion", v)}
                    options={[{ value: "No Afecta", label: "No Afecta" }, { value: "Afectación Parcial", label: "Afectación Parcial" }, { value: "Afecta Disponibilidad", label: "Afecta Disponibilidad" }]} />
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <label className="text-sm font-semibold">Fecha Inicio Ventana</label>
                    <Input type="date" value={fechaInicio} onChange={e => setFechaInicio(e.target.value)} />
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-semibold">Hora Inicio</label>
                    <Input type="time" value={horaInicio} onChange={e => setHoraInicio(e.target.value)} />
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-semibold">Fecha Fin Ventana</label>
                    <Input type="date" value={fechaFin} onChange={e => setFechaFin(e.target.value)} />
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-semibold">Hora Fin</label>
                    <Input type="time" value={horaFin} onChange={e => setHoraFin(e.target.value)} />
                  </div>
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-semibold">Descripción de Tareas</label>
                  <Textarea value={form.descripcion} onChange={e => setForm(f => ({ ...f, descripcion: e.target.value }))} rows={3} placeholder="Describe las tareas del mantenimiento..." />
                </div>
                <div className="flex justify-end pt-4">
                  <Button onClick={irAPaso2} className="gap-2">Siguiente <ArrowRight size={16} /></Button>
                </div>
              </CardContent></Card>
            )}

            {step === 2 && (
              <Card><CardContent className="p-6 space-y-4">
                <h3 className="font-bold text-accent">2. Detalles y Configuración</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2"><label className="text-sm font-semibold">Consecutivo</label>
                    <Input value={consecutivoPreview} disabled /></div>
                  <div className="space-y-2"><label className="text-sm font-semibold">Asunto</label>
                    <Input value={form.asunto} onChange={e => setForm(f => ({ ...f, asunto: e.target.value }))} /></div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2"><label className="text-sm font-semibold">Destinatarios</label>
                    <Textarea value={form.correos} onChange={e => setForm(f => ({ ...f, correos: e.target.value }))} rows={3} placeholder="correo1@empresa.com, correo2@empresa.com" /></div>
                  <div className="space-y-2"><label className="text-sm font-semibold">Plantilla</label>
                    <select className="w-full h-10 rounded-xl border border-input bg-background px-3 text-sm" value={form.plantilla_id} onChange={e => setForm(f => ({ ...f, plantilla_id: e.target.value }))}>
                      <option value="">Seleccionar plantilla...</option>
                      {plantillasFiltradas.map((p: any) => (<option key={p.id} value={String(p.id)}>{p.asunto}</option>))}
                    </select></div>
                </div>
                <div className="flex items-center gap-6 pt-2">
                  <label className="flex items-center gap-2 text-sm cursor-pointer">
                    <input type="checkbox" checked={form.requiere_aprobacion} onChange={e => setForm(f => ({ ...f, requiere_aprobacion: e.target.checked }))} className="rounded border-gray-300 w-4 h-4" />
                    Requiere aprobación</label>
                  <label className="flex items-center gap-2 text-sm cursor-pointer">
                    <input type="checkbox" checked={form.es_externa} onChange={e => setForm(f => ({ ...f, es_externa: e.target.checked }))} className="rounded border-gray-300 w-4 h-4" />
                    Comunicación externa</label>
                </div>
                <div className="flex justify-between pt-4">
                  <Button variant="outline" onClick={() => setStep(1)} className="gap-2"><ArrowLeft size={16} /> Atrás</Button>
                  <Button onClick={generarPreview} disabled={submitting} className="gap-2">
                    {submitting ? <Loader2 size={16} className="animate-spin" /> : <Eye size={16} />} Vista Previa</Button>
                </div>
              </CardContent></Card>
            )}

            {step === 3 && (
              <Card><CardContent className="p-6 space-y-4">
                <h3 className="font-bold text-accent">3. Confirmación</h3>
                <div className="flex items-center gap-2 mb-2">
                  <Badge variant="warning">Pendiente</Badge>
                  <span className="text-xs text-muted-foreground">Verifica el contenido antes de programar</span>
                </div>
                {previewHtml && (
                  <div className="rounded-xl border bg-white overflow-hidden" style={{ height: 450 }}>
                    <iframe srcDoc={previewHtml} width="100%" height="100%" style={{ border: "none" }} title="Preview" />
                  </div>
                )}
                <div className="flex justify-between pt-4">
                  <Button variant="outline" onClick={() => setStep(2)} className="gap-2"><ArrowLeft size={16} /> Editar</Button>
                  <Button onClick={confirmarApertura} disabled={submitting} className="gap-2">
                    {submitting ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
                    {submitting ? "Programando..." : "Generar y Programar"}</Button>
                </div>
              </CardContent></Card>
            )}
          </>
        ) : (
          <div className="space-y-6">
            {selectedMantenimiento ? (
              cierreStep === 1 ? (
                <Card><CardContent className="p-6 space-y-4">
                  <div className="flex items-center gap-2 mb-4">
                    <div className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold bg-primary text-white">1</div>
                    <span className="text-xs font-medium text-accent">Datos de Cierre</span>
                    <div className="flex-1 h-px bg-border" />
                    <div className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold bg-muted text-muted-foreground">2</div>
                    <span className="text-xs font-medium text-muted-foreground">Preview y Confirmar</span>
                    <button className="ml-auto text-xs text-muted-foreground hover:text-accent" onClick={() => setSelectedMantenimiento(null)}><XCircle size={14} className="inline" /> Cancelar</button>
                  </div>
                  <div className="grid grid-cols-2 gap-4 text-sm bg-muted/30 p-4 rounded-xl">
                    <div><strong>Servicio:</strong> {selectedMantenimiento.servicio_nom}</div>
                    <div><strong>Plataforma:</strong> {selectedMantenimiento.plataforma_nom}</div>
                    <div><strong>Afectación:</strong> {selectedMantenimiento.afectacion}</div>
                    <div><strong>Estado:</strong> {selectedMantenimiento.estado}</div>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-2"><label className="text-sm font-semibold">Plantilla de Cierre</label>
                      <select className="w-full h-10 rounded-xl border border-input bg-background px-3 text-sm" value={plantillaCierreId} onChange={e => setPlantillaCierreId(e.target.value)}>
                        <option value="">Seleccionar plantilla...</option>
                        {plantillasCierre.map((p: any) => <option key={p.id} value={String(p.id)}>{p.asunto}</option>)}
                      </select>
                      {plantillasCierre.length === 0 && <p className="text-xs text-amber-600">No hay plantillas FIN_MANTENIMIENTO. Revisa Administración.</p>}
                    </div>
                    <div className="space-y-2"><label className="text-sm font-semibold">Correos</label>
                      <Input value={cierreForm.correos_finales} onChange={e => setCierreForm(f => ({ ...f, correos_finales: e.target.value }))} /></div>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-2"><label className="text-sm font-semibold">Fecha Finalización Real</label>
                      <Input type="date" value={fechaCierreMant} onChange={e => setFechaCierreMant(e.target.value)} /></div>
                    <div className="space-y-2"><label className="text-sm font-semibold">Hora Finalización Real</label>
                      <Input type="time" value={horaCierreMant} onChange={e => setHoraCierreMant(e.target.value)} /></div>
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-semibold">Solución Aplicada</label>
                    <Textarea value={cierreForm.solucion} onChange={e => setCierreForm(f => ({ ...f, solucion: e.target.value }))} rows={3} placeholder="Describe la solución aplicada..." /></div>
                  <div className="space-y-2"><label className="text-sm font-semibold">Asunto Cierre</label>
                    <Input value={cierreForm.asunto_cierre} onChange={e => setCierreForm(f => ({ ...f, asunto_cierre: e.target.value }))} /></div>
                  <div className="flex justify-between pt-4">
                    <Button variant="outline" onClick={() => setSelectedMantenimiento(null)} className="gap-2"><ArrowLeft size={16} /> Volver</Button>
                    <Button onClick={irAPreviewCierre} className="gap-2"><Eye size={16} /> Vista Previa</Button>
                  </div>
                </CardContent></Card>
              ) : (
                <Card><CardContent className="p-6 space-y-4">
                  <div className="flex items-center gap-2 mb-4">
                    <div className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold bg-green-500 text-white"><CheckCircle size={14} /></div>
                    <span className="text-xs font-medium text-green-600">Completado</span>
                    <div className="flex-1 h-px bg-border" />
                    <div className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold bg-primary text-white">2</div>
                    <span className="text-xs font-medium text-accent">Preview y Confirmar</span>
                  </div>
                  {cierrePreviewHtml && (
                    <div className="rounded-xl border bg-white overflow-hidden" style={{ height: 400 }}>
                      <iframe srcDoc={cierrePreviewHtml} width="100%" height="100%" style={{ border: "none" }} title="Cierre Preview" />
                    </div>
                  )}
                  <div className="flex justify-between pt-4">
                    <Button variant="outline" onClick={() => setCierreStep(1)} className="gap-2"><ArrowLeft size={16} /> Editar</Button>
                    <Button onClick={confirmarCierre} disabled={submitting || !cierreForm.solucion} className="gap-2">
                      {submitting ? <Loader2 size={16} className="animate-spin" /> : <CheckCircle size={16} />}
                      {submitting ? "Finalizando..." : "Confirmar Cierre"}</Button>
                  </div>
                </CardContent></Card>
              )
            ) : abiertos.length === 0 ? (
              <Card><CardContent className="p-12 text-center text-muted-foreground">
                <CheckCircle size={48} className="mx-auto mb-3 opacity-30" />
                <p className="font-semibold">No hay ventanas activas</p>
                <p className="text-sm">Todas las ventanas de mantenimiento han sido finalizadas.</p>
              </CardContent></Card>
            ) : (
              <Card><CardContent className="p-6">
                <h3 className="font-bold text-accent mb-4">Ventanas de Mantenimiento Activas</h3>
                <DataTable columns={[
                  { key: "consecutivo_num", header: "Consecutivo" },
                  { key: "servicio_nom", header: "Servicio" },
                  { key: "plataforma_nom", header: "Plataforma" },
                  { key: "afectacion", header: "Afectación", render: (item: any) => <Badge variant={item.afectacion === "Afecta Disponibilidad" ? "danger" : "info"}>{item.afectacion}</Badge> },
                  { key: "fecha_creacion", header: "Creado", render: (item: any) => new Date(item.fecha_creacion).toLocaleDateString("es-CO") },
                  { key: "acciones", header: "Acción", render: (item: any) => <Button size="sm" onClick={() => seleccionarMantenimiento(item)} className="gap-1"><CheckCircle size={14} /> Finalizar</Button> }
                ]} data={abiertos} />
              </CardContent></Card>
            )}
          </div>
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
