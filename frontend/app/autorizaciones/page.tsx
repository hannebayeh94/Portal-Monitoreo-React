"use client";

import { useState, useEffect } from "react";
import { AppShell } from "@/components/layout/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { PageLoader, EmptyState } from "@/components/ui/spinner";
import api from "@/lib/api-client";
import { toast } from "sonner";
import { ShieldCheck, CheckCircle, XCircle, AlertTriangle, Loader2 } from "lucide-react";

export default function AutorizacionesPage() {
  const [pendientes, setPendientes] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionId, setActionId] = useState<number | null>(null);

  const load = () => {
    api.get<any[]>("/comunicados/pending-approval").then(setPendientes).catch(console.error).finally(() => setLoading(false));
  };
  useEffect(load, []);

  const aprobar = async (id: number) => {
    setActionId(id);
    try { await api.post("/comunicados/aprobar/" + id); toast.success("Comunicado aprobado"); load(); }
    catch (e: any) { toast.error(e.message || "Error"); }
    finally { setActionId(null); }
  };

  const rechazar = async (id: number) => {
    setActionId(id);
    try { await api.post("/comunicados/rechazar/" + id); toast.success("Comunicado rechazado"); load(); }
    catch (e: any) { toast.error(e.message || "Error"); }
    finally { setActionId(null); }
  };

  if (loading) return <AppShell><PageLoader /></AppShell>;

  return (
    <AppShell>
      <div className="animate-fade-in space-y-6">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-primary-light"><ShieldCheck className="text-primary" size={24} /></div>
          <div><h1 className="text-2xl font-extrabold text-accent">Bandeja de Autorizaciones</h1>
          <p className="text-sm text-muted-foreground">Comunicados pendientes de aprobación</p></div>
        </div>
        {pendientes.length === 0 ? (
          <EmptyState icon={<CheckCircle className="text-green-500" size={48} />}
            title="No hay comunicados pendientes" description="Todos han sido procesados" />
        ) : (
          <div className="space-y-4">
            {pendientes.map((p: any) => (
              <Card key={p.id}>
                <CardContent className="p-5">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <AlertTriangle className="text-amber-500" size={20} />
                      <span className="font-bold">{p.consecutivo_num}</span>
                      <Badge variant="warning">{p.estado}</Badge>
                    </div>
                    <span className="text-xs text-muted-foreground">{p.servicio_nom}</span>
                  </div>
                  <p className="text-sm mb-1"><b>Asunto:</b> {p.asunto_final}</p>
                  <p className="text-xs text-muted-foreground mb-3">Analista: {p.analista_nom}</p>
                  <div className="flex gap-2">
                    <Button size="sm" onClick={() => aprobar(p.id)} disabled={actionId === p.id} className="gap-1">
                      {actionId === p.id ? <Loader2 size={14} className="animate-spin" /> : <CheckCircle size={14} />}
                      Aprobar
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => rechazar(p.id)} disabled={actionId === p.id} className="gap-1">
                      <XCircle size={14} /> Rechazar
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </AppShell>
  );
}
