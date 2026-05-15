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
import { toast } from "sonner";
import { History, Search, Edit, Send, ArrowLeft, Loader2, Eye, ArrowRight } from "lucide-react";

export default function HistorialPage() {
  const [comunicados, setComunicados] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [selId, setSelId] = useState<number | null>(null);
  const [detalle, setDetalle] = useState<any>(null);
  const [editDesc, setEditDesc] = useState("");
  const [editSol, setEditSol] = useState("");
  const [reenvioTipo, setReenvioTipo] = useState("apertura");
  const [reenvioCorreos, setReenvioCorreos] = useState("");
  const [reenvioMsg, setReenvioMsg] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  const [previewData, setPreviewData] = useState<any>(null);

  const load = () => {
    api.get<any[]>("/comunicados/historial").then(d => {
      setComunicados(d);
      const casoEdit = localStorage.getItem("caso_a_editar");
      if (casoEdit) {
        localStorage.removeItem("caso_a_editar");
        const target = d.find((c: any) => String(c.id) === casoEdit);
        if (target) setTimeout(() => seleccionar(target.id), 100);
      }
    }).catch(console.error).finally(() => setLoading(false));
  };
  useEffect(load, []);

  const seleccionar = async (id: number) => {
    setSelId(id);
    setShowPreview(false);
    setPreviewData(null);
    const d = await api.get<any>("/comunicados/detalle/" + id);
    setDetalle(d);
    setEditDesc(d.descripcion || "");
    setEditSol(d.solucion_aplicada || "");
    setReenvioCorreos((d.emails_originales || []).join(", "));
  };

  const guardarEdicion = async () => {
    if (!selId) return;
    setSubmitting(true);
    try {
      await api.put("/comunicados/" + selId + "/editar", { descripcion: editDesc, solucion: editSol });
      toast.success("Cambios guardados");
      seleccionar(selId);
    } catch (e: any) { toast.error(e.message || "Error"); }
    finally { setSubmitting(false); }
  };

  const generarPreview = () => {
    if (!selId || !detalle) return;
    if (!reenvioCorreos.trim()) { toast.error("Debes ingresar al menos un correo"); return; }
    if (reenvioTipo === "actualizacion" && !reenvioMsg.trim()) {
      toast.error("Debes escribir un mensaje para la actualización"); return;
    }

    let asunto = detalle.asunto_final || "";
    let html = detalle.html_final || "";
    if (reenvioTipo === "cierre" && detalle.html_cierre) {
      asunto = detalle.asunto_cierre || asunto;
      html = detalle.html_cierre;
    } else if (reenvioTipo === "actualizacion") {
      asunto = "ACTUALIZACIÓN: " + asunto;
      const banner = `<div style="background-color:#E3F2FD;border-left:5px solid #2bbcee;padding:15px;margin-bottom:25px;border-radius:4px;"><h3 style="margin-top:0;margin-bottom:8px;color:#10004F;font-family:Arial,sans-serif;font-size:16px;">📢 Actualización de Novedad</h3><p style="margin:0;color:#10004F;font-family:Arial,sans-serif;font-size:14px;line-height:1.5;">${reenvioMsg}</p></div>`;
      if (html.includes('<h1 style="font-size:22px;')) {
        html = html.replace('<h1 style="font-size:22px;', banner + '<h1 style="font-size:22px;');
      } else {
        html = banner + html;
      }
    }

    if (!html) { toast.error("No se encontró el formato HTML original"); return; }

    setPreviewData({ asunto, html, correos: reenvioCorreos });
    setShowPreview(true);
  };

  const confirmarReenvio = async () => {
    if (!selId || !detalle || !previewData) return;
    setSubmitting(true);
    try {
      await api.post("/comunicados/reenviar", {
        com_id: selId, asunto: previewData.asunto, html: previewData.html,
        correos: previewData.correos, tipo_reenvio: reenvioTipo,
        consecutivo: detalle.consecutivo_num
      });
      toast.success("Despachado exitosamente");
      setShowPreview(false);
      setPreviewData(null);
    } catch (e: any) { toast.error(e.message || "Error"); }
    finally { setSubmitting(false); }
  };

  if (loading) return <AppShell><PageLoader /></AppShell>;

  return (
    <AppShell>
      <div className="animate-fade-in space-y-6">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-primary-light"><History className="text-primary" size={24} /></div>
          <div><h1 className="text-2xl font-extrabold text-accent">Historial de Comunicados</h1>
          <p className="text-sm text-muted-foreground">Consulta, edita y reenvía comunicados</p></div>
        </div>
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" size={18} />
          <Input className="pl-10" placeholder="Buscar por asunto..." value={search} onChange={e => setSearch(e.target.value)} />
        </div>
        {!selId ? (
          <Card><CardContent className="p-4 space-y-2">
            {(comunicados.filter((c: any) => !search || (c.asunto || "").toLowerCase().includes(search.toLowerCase()))).map((c: any) => (
              <div key={c.id} onClick={() => seleccionar(c.id)}
                className="flex items-center justify-between p-3 rounded-lg border cursor-pointer hover:bg-muted/50 transition-all">
                <div>
                  <p className="font-semibold text-sm">{c.consecutivo}</p>
                  <p className="text-xs text-muted-foreground">{c.servicio} - {c.estado}</p>
                </div>
                <Badge variant={c.estado === "Cerrado" ? "success" : "warning"}>{c.estado}</Badge>
              </div>
            ))}
          </CardContent></Card>
        ) : showPreview && previewData ? (
          <div className="grid grid-cols-1 gap-6">
            <Card>
              <CardContent className="p-5 space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="font-bold text-accent flex items-center gap-2"><Eye size={18} /> Vista Previa de Despacho</h3>
                  <Button variant="ghost" size="sm" onClick={() => { setShowPreview(false); setPreviewData(null); }}><ArrowLeft size={16} /> Editar</Button>
                </div>
                <div className="rounded-xl bg-muted/30 p-4 text-sm space-y-2">
                  <p><strong>Versión seleccionada:</strong> {reenvioTipo === "apertura" ? "Apertura / Novedad" : reenvioTipo === "cierre" ? "Cierre / Normalidad" : "Actualización de Estado"}</p>
                  <p><strong>Asunto:</strong> {previewData.asunto}</p>
                  <p><strong>Destinatarios (BCC):</strong> {previewData.correos}</p>
                  <p className="text-xs text-muted-foreground">El estado del comunicado no cambiará y no se notificará a correos internos (CC).</p>
                </div>
                {previewData.html && (
                  <div className="rounded-xl border bg-white overflow-hidden" style={{ height: 500 }}>
                    <iframe srcDoc={previewData.html} width="100%" height="100%" style={{ border: "none" }} title="Preview Reenvío" />
                  </div>
                )}
                <div className="flex justify-end gap-3 pt-2">
                  <Button variant="outline" onClick={() => { setShowPreview(false); setPreviewData(null); }} className="gap-2">
                    <ArrowLeft size={16} /> Cancelar
                  </Button>
                  <Button onClick={confirmarReenvio} disabled={submitting} className="gap-2">
                    {submitting ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
                    {submitting ? "Despachando..." : "Confirmar y Despachar"}
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card><CardContent className="p-5 space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="font-bold text-accent flex items-center gap-2"><Edit size={18} /> Editar Textos</h3>
                <Button variant="ghost" size="sm" onClick={() => setSelId(null)}><ArrowLeft size={16} /> Volver</Button>
              </div>
              <div className="space-y-2">
                <label className="text-sm font-semibold">Descripción (Pública)</label>
                <Textarea value={editDesc} onChange={e => setEditDesc(e.target.value)} rows={4} />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-semibold">Solución (Interna)</label>
                <Textarea value={editSol} onChange={e => setEditSol(e.target.value)} rows={4} />
              </div>
              <Button onClick={guardarEdicion} disabled={submitting} className="w-full gap-2">
                {submitting ? <Loader2 size={16} className="animate-spin" /> : null}
                Guardar Cambios
              </Button>
            </CardContent></Card>
            <Card><CardContent className="p-5 space-y-4">
              <h3 className="font-bold text-accent flex items-center gap-2"><Send size={18} /> Despachar / Actualizar</h3>
              <div className="flex gap-2">
                {["apertura", "cierre", "actualizacion"].map(t => (
                  <button key={t} onClick={() => { setReenvioTipo(t); setShowPreview(false); setPreviewData(null); }}
                    className={"px-3 py-1.5 rounded-lg text-xs font-medium transition-all " + (reenvioTipo === t ? "bg-primary text-white" : "bg-muted text-muted-foreground")}>
                    {t === "apertura" ? "Apertura" : t === "cierre" ? "Cierre" : "Actualiz."}
                  </button>
                ))}
              </div>
              {reenvioTipo === "actualizacion" && (
                <Textarea value={reenvioMsg} onChange={e => setReenvioMsg(e.target.value)} rows={2} placeholder="Mensaje de actualización..." />
              )}
              <div className="space-y-2">
                <label className="text-sm font-semibold">Correos</label>
                <Textarea value={reenvioCorreos} onChange={e => setReenvioCorreos(e.target.value)} rows={2} />
              </div>
              <Button onClick={generarPreview} disabled={!reenvioCorreos.trim()} className="w-full gap-2">
                <Eye size={16} /> Vista Previa
              </Button>
            </CardContent></Card>
          </div>
        )}
      </div>
    </AppShell>
  );
}
