"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/layout/app-shell";
import { KPICard } from "@/components/shared/kpi-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PageLoader, EmptyState } from "@/components/ui/spinner";
import { DataTable } from "@/components/shared/data-table";
import api from "@/lib/api-client";
import { formatDate, calcularEstadoSla } from "@/lib/utils";
import {
  Activity, AlertTriangle, CheckCircle, Clock,
  TrendingUp, Zap, Shield, Send, ChevronDown, ChevronUp
} from "lucide-react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, PieChart, Pie, Cell
} from "recharts";

const COLORS = ["#d51b5d", "#2bbcee", "#10004F", "#ffb74d", "#4caf50"];

export default function DashboardPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [slaHoras, setSlaHoras] = useState(4);
  const [expandedAlerts, setExpandedAlerts] = useState<Set<number>>(new Set());
  const router = useRouter();

  useEffect(() => {
    Promise.all([
      api.get("/reportes/dashboard"),
      api.get("/comunicados/config-sla").catch(() => ({ sla_horas: 4 })),
      api.post("/comunicados/sla-check").catch(() => {})
    ]).then(([d, cfg]) => {
      setData(d);
      setSlaHoras(cfg.sla_horas || 4);
    }).catch(console.error).finally(() => setLoading(false));
  }, []);

  const slaIncumplidos = (data?.activos || []).filter((a: any) => {
    const sla = calcularEstadoSla(a.fecha_creacion, slaHoras);
    return sla.label === "Incumplido";
  });

  const toggleAlert = (id: number) => {
    setExpandedAlerts(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const irAHistorial = (id: number) => {
    localStorage.setItem("caso_a_editar", String(id));
    router.push("/historial");
  };

  if (loading) return <AppShell><PageLoader /></AppShell>;

  const kpi = data?.kpi || {};
  const activos = data?.activos || [];
  const tendencia = data?.tendencia || [];
  const topServicios = data?.top_servicios || [];
  const plataformas = data?.plataformas || [];

  return (
    <AppShell>
      <div className="animate-fade-in space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-extrabold text-accent">Centro Operativo SOC</h1>
            <p className="text-muted-foreground text-sm mt-1">Monitoreo en tiempo real de servicios y SLA</p>
          </div>
          <Badge variant="success" className="text-xs gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
            Sistema activo
          </Badge>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <KPICard title="Novedades Activas" value={kpi.activos || 0} icon={<Activity size={20} />} subtitle="Incidentes abiertos" />
          <KPICard title="Resolución Global" value={`${kpi.pct_cierre || 0}%`} icon={<CheckCircle size={20} />}
            trend={{ value: `${kpi.sla_pct || 0}% dentro de SLA`, positive: (kpi.sla_pct || 0) >= 90 }} />
          <KPICard title="MTTR Promedio" value={`${kpi.mttr_min || 0} min`} icon={<Clock size={20} />} subtitle="Tiempo medio de resolución" />
          <KPICard title="SLA Incumplidos" value={kpi.escalados || 0} icon={<AlertTriangle size={20} />}
            trend={{ value: `${slaIncumplidos.length} vencidos ahora`, positive: slaIncumplidos.length === 0 }} />
        </div>

        {/* Alertas Críticas - expandibles con detalles y botón como V35.py */}
        {slaIncumplidos.length > 0 && (
          <div className="rounded-xl border border-red-200 bg-red-50 p-4 animate-slide-in">
            <div className="flex items-center gap-2 mb-3">
              <AlertTriangle className="text-red-600" size={20} />
              <h3 className="font-bold text-red-800">Alertas Críticas (SLA Vencido &gt; {slaHoras}h)</h3>
              <span className="text-xs text-red-600 font-medium ml-auto">{slaIncumplidos.length} caso(s)</span>
            </div>
            <div className="space-y-2">
              {slaIncumplidos.slice(0, 10).map((inc: any) => {
                const isOpen = expandedAlerts.has(inc.id);
                return (
                  <div key={inc.id} className="bg-white rounded-lg border border-red-100 overflow-hidden">
                    <button onClick={() => toggleAlert(inc.id)}
                      className="w-full flex items-center justify-between p-3 hover:bg-red-50/50 transition-colors text-left">
                      <div className="flex items-center gap-3 min-w-0">
                        <span className="w-2 h-2 rounded-full bg-red-500 shrink-0" />
                        <span className="font-semibold text-sm text-red-800">{inc.consecutivo_num}</span>
                        <span className="text-sm text-muted-foreground truncate">{inc.servicio}</span>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <span className="text-xs text-red-600 font-medium">{formatDate(inc.fecha_creacion)}</span>
                        {isOpen ? <ChevronUp size={16} className="text-muted-foreground" /> : <ChevronDown size={16} className="text-muted-foreground" />}
                      </div>
                    </button>
                    {isOpen && (
                      <div className="px-4 pb-4 border-t border-red-100">
                        <div className="mt-3 space-y-2">
                          <p className="text-sm text-accent">
                            <span className="font-semibold">Asunto:</span> {inc.asunto_final || "Sin Asunto"}
                          </p>
                          <p className="text-sm text-accent">
                            <span className="font-semibold">Abierto desde:</span> {formatDate(inc.fecha_creacion)}
                          </p>
                          <div className="bg-red-50/50 p-3 rounded-lg border-l-3 border-red-500 text-sm text-accent">
                            <span className="font-semibold">Descripción de Afectación:</span><br />
                            {inc.descripcion || "Sin detalle registrado."}
                          </div>
                          <div className="pt-1">
                            <Button size="sm" onClick={() => irAHistorial(inc.id)}
                              className="gap-1.5 text-xs" variant="outline">
                              <Send size={14} /> Enviar Actualización
                            </Button>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="rounded-xl border bg-white p-5">
            <h3 className="section-title"><TrendingUp size={18} className="text-primary" /> Tendencia de Eventos (30 días)</h3>
            {tendencia.length > 0 ? (
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={tendencia}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="dia" tick={{ fontSize: 11 }} tickFormatter={(v) => v?.slice(5) || ""} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Bar dataKey="cantidad" fill="#d51b5d" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : <EmptyState title="Sin datos" description="No hay eventos en los últimos 30 días" />}
          </div>
          <div className="rounded-xl border bg-white p-5">
            <h3 className="section-title"><Zap size={18} className="text-primary" /> Top Servicios con Incidentes</h3>
            {topServicios.length > 0 ? (
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={topServicios} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis type="number" tick={{ fontSize: 11 }} />
                  <YAxis dataKey="nombre" type="category" tick={{ fontSize: 11 }} width={120} />
                  <Tooltip />
                  <Bar dataKey="cantidad" fill="#2bbcee" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : <EmptyState title="Sin datos" description="No hay suficientes datos" />}
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2">
            <div className="rounded-xl border bg-white p-5">
              <h3 className="section-title"><Activity size={18} className="text-primary" /> Novedades Pendientes (Monitor SLA)</h3>
              {activos.length > 0 ? (
                <DataTable columns={[
                  { key: "sla", header: "SLA", render: (item) => {
                    const sla = calcularEstadoSla(item.fecha_creacion, slaHoras);
                    return <Badge variant={sla.label === "Incumplido" ? "danger" : sla.label === "En Riesgo" ? "warning" : "success"}>{sla.label}</Badge>;
                  }},
                  { key: "consecutivo_num", header: "ID" },
                  { key: "servicio", header: "Servicio" },
                  { key: "fecha_creacion", header: "Apertura", render: (item) => formatDate(item.fecha_creacion) },
                  { key: "afectacion", header: "Afectación", render: (item) => (
                    <Badge variant={item.afectacion === "Afecta Disponibilidad" ? "danger" : item.afectacion === "Afectación Parcial" ? "warning" : "info"}>{item.afectacion || "N/A"}</Badge>
                  )},
                  { key: "accion", header: "", render: (item) => (
                    <Button variant="ghost" size="sm" onClick={() => irAHistorial(item.id)} className="gap-1 text-xs">
                      <Send size={12} /> Ir
                    </Button>
                  )},
                ]} data={activos} />
              ) : (
                <EmptyState icon={<CheckCircle className="text-green-500" size={40} />} title="Todo en orden" description="No hay novedades abiertas en este momento" />
              )}
            </div>
          </div>
          <div>
            <div className="rounded-xl border bg-white p-5">
              <h3 className="section-title"><Shield size={18} className="text-primary" /> Incidentes por Plataforma</h3>
              {plataformas.length > 0 ? (
                <>
                  <ResponsiveContainer width="100%" height={280}>
                    <PieChart>
                      <Pie data={plataformas} dataKey="cantidad" nameKey="nombre" cx="50%" cy="50%" innerRadius={60} outerRadius={100} paddingAngle={3}>
                        {plataformas.map((_: any, idx: number) => <Cell key={idx} fill={COLORS[idx % COLORS.length]} />)}
                      </Pie>
                      <Tooltip />
                    </PieChart>
                  </ResponsiveContainer>
                  <div className="flex flex-wrap gap-2 mt-3 justify-center">
                    {plataformas.map((p: any, idx: number) => (
                      <div key={p.nombre} className="flex items-center gap-1.5 text-xs">
                        <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: COLORS[idx % COLORS.length] }} />
                        <span className="text-muted-foreground">{p.nombre}: {p.cantidad}</span>
                      </div>
                    ))}
                  </div>
                </>
              ) : <EmptyState title="Sin datos" description="No hay plataformas registradas" />}
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
