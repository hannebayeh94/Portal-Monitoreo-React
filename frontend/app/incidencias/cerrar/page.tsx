"use client";

import { useState, useEffect } from "react";
import { AppShell } from "@/components/layout/app-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { PageLoader, EmptyState } from "@/components/ui/spinner";
import api from "@/lib/api-client";
import { formatFechaEs } from "@/lib/utils";
import { toast } from "sonner";
import { CheckSquare, ArrowLeft, Send, Loader2, Eye, FileText } from "lucide-react";

interface Comunicado {
  id: number; consecutivo_num: string; asunto_final: string;
  servicio_nom: string; fecha_creacion: string; descripcion: string;
  servicio_id: number; plataforma_id: number; tipo_comunicado_id: number;
  tercero_id: number | null; tercero_nom: string | null;
  emails_apertura: string; plataforma_nom: string; html_final: string;
  tipo_comunicado_nom: string;
}

interface Plantilla { id: number; plataforma_id: number | null; tipo_comunicado_id: number; asunto: string; html: string; }

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

export default function CerrarNovedadPage() {
  const [incidentes, setIncidentes] = useState<Comunicado[]>([]);
  const [catalogos, setCatalogos] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [step, setStep] = useState(1);
  const [selInc, setSelInc] = useState<Comunicado | null>(null);
  const [asunto, setAsunto] = useState("");
  const [descripcion, setDescripcion] = useState("");
  const [solucion, setSolucion] = useState("");
  const [correos, setCorreos] = useState("");
  const [fechaCierre, setFechaCierre] = useState(toDateInput(hoy()));
  const [horaCierre, setHoraCierre] = useState(toTimeInput(hoy()));
  const [plantillasFiltradas, setPlantillasFiltradas] = useState<Plantilla[]>([]);
  const [plantillaId, setPlantillaId] = useState("");
  const [previewHtml, setPreviewHtml] = useState("");

  useEffect(() => {
    Promise.all([
      api.get<Comunicado[]>("/comunicados/abiertos?tipo=incidente"),
      api.get<any>("/comunicados/catalogos")
    ]).then(([d, cat]) => {
      setIncidentes(d);
      setCatalogos(cat);
    }).catch(console.error).finally(() => setLoading(false));
  }, []);

  const seleccionar = (inc: Comunicado) => {
    setSelInc(inc);
    setAsunto(inc.consecutivo_num + " - Comunicado de Normalidad - " + inc.servicio_nom);
    setDescripcion("El servicio de " + inc.servicio_nom + " ha sido restablecido y opera con normalidad.");
    try {
      const jsn = JSON.parse(inc.emails_apertura || "[]");
      setCorreos(Array.isArray(jsn) ? jsn.join(", ") : "");
    } catch { setCorreos(""); }
    setStep(1);

    const plantillas = (catalogos?.plantillas || []).filter((p: Plantilla) => {
      if (p.tipo_comunicado_id !== inc.tipo_comunicado_id) return false;
      if (inc.plataforma_id && p.plataforma_id && p.plataforma_id !== inc.plataforma_id) return false;
      return true;
    });
    const kw_cierre = ["cierre", "normalidad", "consaldo", "fin", "restablecimiento", "solucion"];
    const filtradas = plantillas.filter((p: Plantilla) =>
      kw_cierre.some(kw => p.asunto.toLowerCase().replace(/\s/g, "").includes(kw))
    );
    const finalPlantillas = filtradas.length > 0 ? filtradas : plantillas;
    setPlantillasFiltradas(finalPlantillas);
    if (finalPlantillas.length >= 1) setPlantillaId(String(finalPlantillas[0].id));
    setPreviewHtml("");
  };

  const irAPreview = () => {
    if (!plantillaId) { toast.error("Selecciona una plantilla de cierre"); return; }
    if (!selInc) return;

    const cierreDt = new Date(`${fechaCierre}T${horaCierre}`);
    if (cierreDt < new Date(selInc.fecha_creacion)) {
      toast.error("La fecha/hora de cierre no puede ser anterior a la creación"); return;
    }
    if (cierreDt > new Date()) {
      toast.error("La fecha/hora de cierre no puede ser futura"); return;
    }

    const segundos = Math.floor((cierreDt.getTime() - new Date(selInc.fecha_creacion).getTime()) / 1000);
    const tiempoStr = segundos >= 3600
      ? `${Math.floor(segundos / 3600)}h ${Math.floor((segundos % 3600) / 60)}m`
      : `${Math.floor(segundos / 60)}m`;

    const plant = plantillasFiltradas.find((p: any) => String(p.id) === plantillaId);
    const templateArgs = {
      consecutivo: selInc.consecutivo_num,
      servicio: selInc.servicio_nom || "",
      descripcion_novedad: selInc.descripcion || "",
      descripcion_cierre: descripcion,
      cliente: selInc.tercero_nom || "",
      fecha_comunicado: formatFechaEs(hoy()),
      fecha_inicio: formatFechaEs(new Date(selInc.fecha_creacion)),
      fecha_cierre: formatFechaEs(cierreDt),
      tiempo_transcurrido: tiempoStr,
    };

    const html = renderTemplate(plant?.html || "", templateArgs);
    setPreviewHtml(html);
    setStep(2);
  };

  const confirmarCierre = async () => {
    if (!selInc) return;
    const cierreDt = new Date(`${fechaCierre}T${horaCierre}`);
    setSubmitting(true);
    try {
      await api.post("/comunicados/cierre/" + selInc.id, {
        solucion_interna: solucion, asunto_norm: asunto, html: previewHtml,
        correos_finales: correos, requiere_aprobacion: false,
        fecha_hora_cierre: cierreDt.toISOString()
      });
      toast.success("Incidente cerrado exitosamente");
      setSelInc(null); setSolucion(""); setStep(1); setPreviewHtml("");
      setIncidentes(prev => prev.filter(c => String(c.id) !== String(selInc.id)));
    } catch (e: any) { toast.error(e.message || "Error"); }
    finally { setSubmitting(false); }
  };

  if (loading) return <AppShell><PageLoader /></AppShell>;

  return (
    <AppShell>
      <div className="max-w-4xl mx-auto animate-fade-in space-y-6">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-primary-light"><CheckSquare className="text-primary" size={24} /></div>
          <div><h1 className="text-2xl font-extrabold text-accent">Cierre de Novedad</h1>
          <p className="text-sm text-muted-foreground">Registra la solución con preview antes de confirmar</p></div>
        </div>

        {incidentes.length === 0 && !selInc ? (
          <EmptyState icon={<CheckSquare className="text-green-500" size={40} />}
            title="No hay incidentes abiertos" description="Todos los incidentes han sido resueltos" />
        ) : !selInc ? (
          <Card><CardContent className="p-6 space-y-4">
            <h3 className="font-bold text-accent">1. Seleccionar Novedad a Cerrar</h3>
            {incidentes.map(inc => (
              <div key={inc.id} onClick={() => seleccionar(inc)}
                className="flex items-center justify-between p-4 rounded-xl border cursor-pointer hover:bg-muted/50 hover:border-primary transition-all">
                <div>
                  <p className="font-semibold">{inc.consecutivo_num}</p>
                  <p className="text-sm text-muted-foreground">{inc.servicio_nom} - {inc.asunto_final}</p>
                </div>
                <Badge variant="warning">Abierto</Badge>
              </div>
            ))}
          </CardContent></Card>
        ) : step === 1 ? (
          <Card><CardContent className="p-6 space-y-4">
            <div className="flex items-center gap-2 mb-4">
              <div className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold bg-primary text-white">1</div>
              <span className="text-xs font-medium text-accent">Datos de Cierre</span>
              <div className="flex-1 h-px bg-border" />
              <div className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold bg-muted text-muted-foreground">2</div>
              <span className="text-xs font-medium text-muted-foreground">Preview y Confirmar</span>
            </div>

            <div className="bg-muted/30 p-3 rounded-xl text-sm grid grid-cols-2 gap-2">
              <span><strong>Caso:</strong> {selInc.consecutivo_num}</span>
              <span><strong>Servicio:</strong> {selInc.servicio_nom}</span>
              <span><strong>Creado:</strong> {new Date(selInc.fecha_creacion).toLocaleString("es-CO")}</span>
              <span><strong>Asunto:</strong> {selInc.asunto_final}</span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="text-sm font-semibold">Plantilla de Cierre</label>
                <select className="w-full h-10 rounded-xl border border-input bg-background px-3 text-sm"
                  value={plantillaId} onChange={e => setPlantillaId(e.target.value)}>
                  <option value="">Seleccionar plantilla...</option>
                  {plantillasFiltradas.map((p: Plantilla) => (
                    <option key={p.id} value={String(p.id)}>{p.asunto}</option>
                  ))}
                </select>
                {plantillasFiltradas.length === 0 && <p className="text-xs text-amber-600">No hay plantillas de cierre para este tipo. Revisa la configuración en Administración.</p>}
              </div>
              <div className="space-y-2">
                <label className="text-sm font-semibold">Destinatarios</label>
                <Input value={correos} onChange={e => setCorreos(e.target.value)} />
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2"><label className="text-sm font-semibold">Fecha Cierre</label>
                <Input type="date" value={fechaCierre} onChange={e => setFechaCierre(e.target.value)} /></div>
              <div className="space-y-2"><label className="text-sm font-semibold">Hora Cierre</label>
                <Input type="time" value={horaCierre} onChange={e => setHoraCierre(e.target.value)} /></div>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-semibold">Descripción de Normalidad</label>
              <Textarea value={descripcion} onChange={e => setDescripcion(e.target.value)} rows={3} />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-semibold">Solución Técnica (Interno)</label>
              <Textarea value={solucion} onChange={e => setSolucion(e.target.value)} rows={3} placeholder="Describe la solución aplicada..." />
            </div>

            <div className="flex justify-between pt-4">
              <Button variant="outline" onClick={() => { setSelInc(null); setStep(1); }} className="gap-2"><ArrowLeft size={16} /> Atrás</Button>
              <Button onClick={irAPreview} className="gap-2"><Eye size={16} /> Vista Previa</Button>
            </div>
          </CardContent></Card>
        ) : (
          <Card><CardContent className="p-6 space-y-4">
            <div className="flex items-center gap-2 mb-4">
              <div className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold bg-green-500 text-white"><CheckSquare size={14} /></div>
              <span className="text-xs font-medium text-green-600">Completado</span>
              <div className="flex-1 h-px bg-border" />
              <div className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold bg-primary text-white">2</div>
              <span className="text-xs font-medium text-accent">Preview y Confirmar</span>
            </div>

            <div className="flex items-center gap-2 mb-2">
              <Badge variant="warning">Revisar antes de cerrar</Badge>
              <span className="text-xs text-muted-foreground">Verifica el contenido del cierre</span>
            </div>
            {previewHtml && (
              <div className="rounded-xl border bg-white overflow-hidden" style={{ height: 450 }}>
                <iframe srcDoc={previewHtml} width="100%" height="100%" style={{ border: "none" }} title="Preview Cierre" />
              </div>
            )}
            <div className="flex justify-between pt-4">
              <Button variant="outline" onClick={() => setStep(1)} className="gap-2"><ArrowLeft size={16} /> Editar</Button>
              <Button onClick={confirmarCierre} disabled={submitting} className="gap-2">
                {submitting ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
                {submitting ? "Cerrando..." : "Confirmar Cierre"}
              </Button>
            </div>
          </CardContent></Card>
        )}
      </div>
    </AppShell>
  );
}
