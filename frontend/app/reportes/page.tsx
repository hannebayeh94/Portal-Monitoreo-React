"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { AppShell } from "@/components/layout/app-shell";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { PageLoader, EmptyState } from "@/components/ui/spinner";
import { DataTable } from "@/components/shared/data-table";
import { KPICard } from "@/components/shared/kpi-card";
import api from "@/lib/api-client";
import { formatDate } from "@/lib/utils";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, PieChart, Pie, Cell,
  AreaChart, Area, ScatterChart, Scatter, Treemap,
  HeatMap, Radar, RadarChart, PolarGrid, PolarAngleAxis,
  PolarRadiusAxis, Legend
} from "recharts";
import {
  Activity, AlertTriangle, Clock, CheckCircle,
  FileSpreadsheet, BarChart3, Download, TrendingUp,
  TrendingDown, Filter, X, Search, Calendar,
  Table2, PieChart as PieChartIcon, LayoutGrid,
  Sun, Eye
} from "lucide-react";
import { toast } from "sonner";

const COLORS = ["#d51b5d", "#2bbcee", "#10004F", "#ffb74d", "#4caf50", "#8e24aa", "#00acc1", "#ff6f00", "#1a237e", "#33691e"];

function formatMinutes(min: number): string {
  if (!min || min <= 0) return "N/A";
  return min >= 60 ? `${Math.floor(min / 60)}h ${Math.floor(min % 60)}m` : `${Math.floor(min)}m`;
}

export default function ReportesPage() {
  const [allData, setAllData] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [exportLoading, setExportLoading] = useState(false);
  const [activeTab, setActiveTab] = useState("resumen");

  const [filtroFechaInicio, setFiltroFechaInicio] = useState("");
  const [filtroFechaFin, setFiltroFechaFin] = useState("");
  const [filtroServicios, setFiltroServicios] = useState<string[]>([]);
  const [filtroPlataformas, setFiltroPlataformas] = useState<string[]>([]);
  const [filtroTipos, setFiltroTipos] = useState<string[]>([]);
  const [filtroAnalistas, setFiltroAnalistas] = useState<string[]>([]);
  const [filtroEstados, setFiltroEstados] = useState<string[]>([]);

  const [serviciosUnicos, setServiciosUnicos] = useState<string[]>([]);
  const [plataformasUnicas, setPlataformasUnicas] = useState<string[]>([]);
  const [tiposUnicos, setTiposUnicos] = useState<string[]>([]);
  const [analistasUnicos, setAnalistasUnicos] = useState<string[]>([]);
  const [estadosUnicos, setEstadosUnicos] = useState<string[]>([]);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const res: any = await api.get("/reportes/export");
      setAllData(res.data || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  useEffect(() => {
    if (allData.length === 0) return;
    setServiciosUnicos([...new Set(allData.map((d: any) => d.servicio).filter(Boolean))].sort() as string[]);
    setPlataformasUnicas([...new Set(allData.map((d: any) => d.plataforma).filter(Boolean))].sort() as string[]);
    setTiposUnicos([...new Set(allData.map((d: any) => d.tipo).filter(Boolean))].sort() as string[]);
    setAnalistasUnicos([...new Set(allData.map((d: any) => d.analista).filter(Boolean))].sort() as string[]);
    setEstadosUnicos([...new Set(allData.map((d: any) => d.estado).filter(Boolean))].sort() as string[]);
  }, [allData]);

  const datosFiltrados = useCallback(() => {
    let data = [...allData];
    if (filtroFechaInicio) data = data.filter((d: any) => d.fecha_creacion >= filtroFechaInicio);
    if (filtroFechaFin) data = data.filter((d: any) => d.fecha_creacion <= filtroFechaFin + " 23:59:59");
    if (filtroServicios.length) data = data.filter((d: any) => filtroServicios.includes(d.servicio));
    if (filtroPlataformas.length) data = data.filter((d: any) => filtroPlataformas.includes(d.plataforma));
    if (filtroTipos.length) data = data.filter((d: any) => filtroTipos.includes(d.tipo));
    if (filtroAnalistas.length) data = data.filter((d: any) => filtroAnalistas.includes(d.analista));
    if (filtroEstados.length) data = data.filter((d: any) => filtroEstados.includes(d.estado));
    return data;
  }, [allData, filtroFechaInicio, filtroFechaFin, filtroServicios, filtroPlataformas, filtroTipos, filtroAnalistas, filtroEstados]);

  const df = datosFiltrados();
  const total = df.length;
  const cerrados = df.filter((d: any) => d.estado === "Cerrado").length;
  const pctCierre = total > 0 ? Math.round(cerrados / total * 100) : 0;
  const escalados = df.filter((d: any) => d.escalado).length;
  const slaPct = total > 0 ? Math.round((total - escalados) / total * 100) : 100;

  const cerradosConTiempo = df.filter((d: any) => d.fecha_creacion && d.fecha_envio && d.estado === "Cerrado");
  const mttr = cerradosConTiempo.length > 0
    ? Math.round(cerradosConTiempo.reduce((sum: number, d: any) => {
        const inicio = new Date(d.fecha_creacion).getTime();
        const fin = new Date(d.fecha_envio).getTime();
        return sum + Math.max(0, (fin - inicio) / 60000);
      }, 0) / cerradosConTiempo.length)
    : 0;

  const topServicios = Object.entries(
    df.reduce((acc: any, d: any) => { acc[d.servicio] = (acc[d.servicio] || 0) + 1; return acc; }, {})
  ).sort((a: any, b: any) => b[1] - a[1]).slice(0, 10).map(([nombre, cantidad]) => ({ nombre, cantidad }));

  const platformasCount = Object.entries(
    df.reduce((acc: any, d: any) => { acc[d.plataforma] = (acc[d.plataforma] || 0) + 1; return acc; }, {})
  ).map(([nombre, cantidad]) => ({ nombre, cantidad }));

  const tendencia = (() => {
    const map: Record<string, number> = {};
    df.forEach((d: any) => {
      if (d.fecha_creacion) {
        const dia = d.fecha_creacion.slice(0, 10);
        map[dia] = (map[dia] || 0) + 1;
      }
    });
    return Object.entries(map).sort(([a], [b]) => a.localeCompare(b)).map(([dia, cantidad]) => ({ dia, cantidad }));
  })();

  const tiposCount = Object.entries(
    df.reduce((acc: any, d: any) => { acc[d.tipo] = (acc[d.tipo] || 0) + 1; return acc; }, {})
  ).map(([nombre, cantidad]) => ({ nombre, cantidad }));

  const proveedoresCount = Object.entries(
    df.reduce((acc: any, d: any) => { acc[d.tercero_nom] = (acc[d.tercero_nom] || 0) + 1; return acc; }, {})
  ).sort((a: any, b: any) => b[1] - a[1]).slice(0, 10).map(([nombre, cantidad]) => ({ nombre: nombre === "N/A" ? "Sin tercero" : nombre, cantidad }));

  const productividad = (() => {
    const map: Record<string, { casos: number; totalMin: number }> = {};
    cerradosConTiempo.forEach((d: any) => {
      if (!d.analista) return;
      if (!map[d.analista]) map[d.analista] = { casos: 0, totalMin: 0 };
      map[d.analista].casos++;
      map[d.analista].totalMin += Math.max(0, (new Date(d.fecha_envio).getTime() - new Date(d.fecha_creacion).getTime()) / 60000);
    });
    return Object.entries(map).map(([analista, v]) => ({
      analista, Casos: v.casos, MTTR: Math.round(v.totalMin / v.casos)
    }));
  })();

  const horaDist = (() => {
    const h: Record<number, number> = {};
    for (let i = 0; i < 24; i++) h[i] = 0;
    df.forEach((d: any) => {
      if (d.fecha_creacion) {
        const hr = new Date(d.fecha_creacion).getHours();
        h[hr] = (h[hr] || 0) + 1;
      }
    });
    return Object.entries(h).map(([hora, cantidad]) => ({ hora: Number(hora), cantidad }));
  })();

  const diaDist = (() => {
    const dias = ["Domingo", "Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"];
    const h: Record<string, number> = {};
    dias.forEach(d => h[d] = 0);
    df.forEach((d: any) => {
      if (d.fecha_creacion) {
        const dia = new Date(d.fecha_creacion).getDay();
        h[dias[dia]]++;
      }
    });
    return Object.entries(h).map(([nombre, cantidad]) => ({ nombre, cantidad }));
  })();

  const limpiarFiltros = () => {
    setFiltroFechaInicio(""); setFiltroFechaFin("");
    setFiltroServicios([]); setFiltroPlataformas([]);
    setFiltroTipos([]); setFiltroAnalistas([]); setFiltroEstados([]);
  };

  const hayFiltros = filtroFechaInicio || filtroFechaFin || filtroServicios.length || filtroPlataformas.length ||
    filtroTipos.length || filtroAnalistas.length || filtroEstados.length;

  const exportarExcel = async () => {
    setExportLoading(true);
    try {
      const res = await fetch("http://localhost:8000/reportes/export", {
        headers: { Authorization: "Bearer " + localStorage.getItem("access_token") }
      });
      const json = await res.json();
      const rows = json.data || [];
      const csv = [
        ["Consecutivo", "Servicio", "Plataforma", "Tipo", "Estado", "Afectación", "Creación", "Cierre", "Escalado", "Analista"],
        ...rows.map((r: any) => [
          r.consecutivo_num, r.servicio, r.plataforma, r.tipo, r.estado,
          r.afectacion, r.fecha_creacion || "", r.fecha_envio || "",
          r.escalado ? "Sí" : "No", r.analista
        ])
      ].map(row => row.map(c => `"${String(c || "").replace(/"/g, '""')}"`).join(",")).join("\n");

      const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `Reporte_TI_${new Date().toISOString().slice(0, 10)}.csv`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success("Reporte exportado exitosamente");
    } catch (e: any) {
      toast.error(e.message || "Error al exportar");
    } finally {
      setExportLoading(false);
    }
  };

  const tabs = [
    { id: "resumen", label: "Resumen Ejecutivo", icon: BarChart3 },
    { id: "kpis", label: "KPIs Operación", icon: Activity },
    { id: "gestion", label: "KPIs Gestión", icon: TrendingUp },
    { id: "tendencias", label: "Tendencias", icon: TrendingDown },
    { id: "horario", label: "Horario Crítico", icon: Sun },
    { id: "datos", label: "Datos Detallados", icon: Table2 },
    { id: "exportar", label: "Exportación", icon: Download },
  ];

  if (loading) return <AppShell><PageLoader /></AppShell>;

  return (
    <AppShell>
      <div className="animate-fade-in space-y-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-primary-light"><BarChart3 className="text-primary" size={24} /></div>
            <div><h1 className="text-2xl font-extrabold text-accent">Informes y Métricas</h1>
            <p className="text-sm text-muted-foreground">Analítica avanzada de operaciones TI</p></div>
          </div>
          <Button variant="outline" onClick={exportarExcel} disabled={exportLoading} className="gap-2">
            <Download size={16} /> {exportLoading ? "Exportando..." : "Exportar CSV"}
          </Button>
        </div>

        {/* Filtros avanzados */}
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-2 mb-3">
              <Filter size={16} className="text-primary" />
              <span className="font-semibold text-sm text-accent">Filtros Avanzados</span>
              {hayFiltros && (
                <button onClick={limpiarFiltros} className="ml-auto text-xs text-primary hover:underline flex items-center gap-1">
                  <X size={12} /> Limpiar filtros
                </button>
              )}
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
              <div className="space-y-1">
                <label className="text-xs font-semibold text-muted-foreground">Fecha Inicio</label>
                <Input type="date" size={1} className="h-9 text-xs" value={filtroFechaInicio} onChange={e => setFiltroFechaInicio(e.target.value)} />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-semibold text-muted-foreground">Fecha Fin</label>
                <Input type="date" size={1} className="h-9 text-xs" value={filtroFechaFin} onChange={e => setFiltroFechaFin(e.target.value)} />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-semibold text-muted-foreground">Servicio</label>
                <select className="w-full h-9 rounded-lg border border-input bg-background px-2 text-xs" multiple value={filtroServicios}
                  onChange={e => setFiltroServicios(Array.from(e.target.selectedOptions, o => o.value))}>
                  {serviciosUnicos.map(s => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
              <div className="space-y-1">
                <label className="text-xs font-semibold text-muted-foreground">Plataforma</label>
                <select className="w-full h-9 rounded-lg border border-input bg-background px-2 text-xs" multiple value={filtroPlataformas}
                  onChange={e => setFiltroPlataformas(Array.from(e.target.selectedOptions, o => o.value))}>
                  {plataformasUnicas.map(s => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
              <div className="space-y-1">
                <label className="text-xs font-semibold text-muted-foreground">Tipo</label>
                <select className="w-full h-9 rounded-lg border border-input bg-background px-2 text-xs" multiple value={filtroTipos}
                  onChange={e => setFiltroTipos(Array.from(e.target.selectedOptions, o => o.value))}>
                  {tiposUnicos.map(s => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
              <div className="space-y-1">
                <label className="text-xs font-semibold text-muted-foreground">Analista</label>
                <select className="w-full h-9 rounded-lg border border-input bg-background px-2 text-xs" multiple value={filtroAnalistas}
                  onChange={e => setFiltroAnalistas(Array.from(e.target.selectedOptions, o => o.value))}>
                  {analistasUnicos.map(s => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
              <div className="space-y-1">
                <label className="text-xs font-semibold text-muted-foreground">Estado</label>
                <select className="w-full h-9 rounded-lg border border-input bg-background px-2 text-xs" multiple value={filtroEstados}
                  onChange={e => setFiltroEstados(Array.from(e.target.selectedOptions, o => o.value))}>
                  {estadosUnicos.map(s => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Tabs de navegación */}
        <div className="flex gap-1 p-1 rounded-xl bg-muted overflow-x-auto">
          {tabs.map(tab => {
            const Icon = tab.icon;
            return (
              <button key={tab.id} onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium whitespace-nowrap transition-all ${
                  activeTab === tab.id ? "bg-white text-accent shadow-sm" : "text-muted-foreground hover:text-accent"
                }`}>
                <Icon size={14} /> {tab.label}
              </button>
            );
          })}
        </div>

        {/* ===== TAB: RESUMEN EJECUTIVO ===== */}
        {activeTab === "resumen" && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <KPICard title="Total Eventos" value={total} icon={<Activity size={20} />}
                subtitle={hayFiltros ? "Filtrados" : "Histórico"} />
              <KPICard title="Tasa de Cierre" value={`${pctCierre}%`} icon={<CheckCircle size={20} />}
                trend={{ value: `${cerrados} cerrados`, positive: pctCierre > 50 }} />
              <KPICard title="MTTR Promedio" value={formatMinutes(mttr)} icon={<Clock size={20} />} />
              <KPICard title="SLA Cumplimiento" value={`${slaPct}%`} icon={<AlertTriangle size={20} />}
                trend={{ value: `${escalados} fuera de SLA`, positive: slaPct >= 90 }} />
            </div>

            {escalados > 0 && (
              <div className="rounded-xl border border-red-200 bg-red-50 p-4">
                <p className="font-semibold text-red-800 text-sm">⚠ {escalados} incidente(s) escalado(s) por SLA en el período seleccionado</p>
              </div>
            )}

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <Card>
                <CardContent className="p-5">
                  <h3 className="font-bold text-accent mb-4 flex items-center gap-2">
                    <TrendingUp size={18} className="text-primary" /> Evolución de Incidentes
                  </h3>
                  {tendencia.length > 0 ? (
                    <ResponsiveContainer width="100%" height={280}>
                      <AreaChart data={tendencia}>
                        <defs><linearGradient id="colorEv" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#d51b5d" stopOpacity={0.3} />
                          <stop offset="95%" stopColor="#d51b5d" stopOpacity={0} />
                        </linearGradient></defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                        <XAxis dataKey="dia" tick={{ fontSize: 11 }} tickFormatter={v => v?.slice(5) || ""} />
                        <YAxis tick={{ fontSize: 11 }} />
                        <Tooltip />
                        <Area type="monotone" dataKey="cantidad" stroke="#d51b5d" fill="url(#colorEv)" strokeWidth={2} />
                      </AreaChart>
                    </ResponsiveContainer>
                  ) : <EmptyState title="Sin datos" />}
                </CardContent>
              </Card>

              <Card>
                <CardContent className="p-5">
                  <h3 className="font-bold text-accent mb-4 flex items-center gap-2">
                    <TrendingDown size={18} className="text-primary" /> Top 10 Servicios
                  </h3>
                  {topServicios.length > 0 ? (
                    <ResponsiveContainer width="100%" height={280}>
                      <BarChart data={topServicios} layout="vertical">
                        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                        <XAxis type="number" tick={{ fontSize: 11 }} />
                        <YAxis dataKey="nombre" type="category" tick={{ fontSize: 11 }} width={120} />
                        <Tooltip />
                        <Bar dataKey="cantidad" fill="#2bbcee" radius={[0, 6, 6, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  ) : <EmptyState title="Sin datos" />}
                </CardContent>
              </Card>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <Card>
                <CardContent className="p-5">
                  <h3 className="font-bold text-accent mb-4">Por Plataforma</h3>
                  {platformasCount.length > 0 ? (
                    <ResponsiveContainer width="100%" height={250}>
                      <PieChart>
                        <Pie data={platformasCount} dataKey="cantidad" nameKey="nombre"
                          cx="50%" cy="50%" innerRadius={50} outerRadius={90} paddingAngle={3}>
                          {platformasCount.map((_: any, i: number) => (
                            <Cell key={i} fill={COLORS[i % COLORS.length]} />
                          ))}
                        </Pie>
                        <Tooltip />
                      </PieChart>
                    </ResponsiveContainer>
                  ) : <EmptyState title="Sin datos" />}
                  <div className="flex flex-wrap gap-2 mt-3 justify-center">
                    {platformasCount.map((p: any, i: number) => (
                      <div key={p.nombre} className="flex items-center gap-1.5 text-xs">
                        <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: COLORS[i % COLORS.length] }} />
                        <span className="text-muted-foreground">{p.nombre}: {p.cantidad}</span>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardContent className="p-5">
                  <h3 className="font-bold text-accent mb-4">Por Tipo de Evento</h3>
                  {tiposCount.length > 0 ? (
                    <ResponsiveContainer width="100%" height={250}>
                      <PieChart>
                        <Pie data={tiposCount} dataKey="cantidad" nameKey="nombre"
                          cx="50%" cy="50%" innerRadius={40} outerRadius={90} paddingAngle={2}>
                          {tiposCount.map((_: any, i: number) => (
                            <Cell key={i} fill={COLORS[(i + 3) % COLORS.length]} />
                          ))}
                        </Pie>
                        <Tooltip />
                      </PieChart>
                    </ResponsiveContainer>
                  ) : <EmptyState title="Sin datos" />}
                </CardContent>
              </Card>

              <Card>
                <CardContent className="p-5">
                  <h3 className="font-bold text-accent mb-4">Top Proveedores</h3>
                  {proveedoresCount.length > 0 ? (
                    <ResponsiveContainer width="100%" height={250}>
                      <BarChart data={proveedoresCount} layout="vertical">
                        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                        <XAxis type="number" tick={{ fontSize: 11 }} />
                        <YAxis dataKey="nombre" type="category" tick={{ fontSize: 10 }} width={100} />
                        <Tooltip />
                        <Bar dataKey="cantidad" fill="#8e24aa" radius={[0, 4, 4, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  ) : <EmptyState title="Sin datos" />}
                </CardContent>
              </Card>
            </div>
          </div>
        )}

        {/* ===== TAB: KPIs OPERACIÓN ===== */}
        {activeTab === "kpis" && (
          <div className="space-y-6">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <KPICard title="Total Eventos" value={total} />
              <KPICard title="Cerrados" value={cerrados} subtitle={`${pctCierre}% del total`} />
              <KPICard title="SLA Incumplidos" value={escalados}
                trend={{ value: `${slaPct}% cumplimiento`, positive: slaPct >= 90 }} />
              <KPICard title="MTTR" value={formatMinutes(mttr)} />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <Card>
                <CardContent className="p-5">
                  <h3 className="font-bold text-accent mb-4">Incidentes por Proveedor</h3>
                  {proveedoresCount.length > 0 ? (
                    <ResponsiveContainer width="100%" height={300}>
                      <BarChart data={proveedoresCount}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                        <XAxis dataKey="nombre" tick={{ fontSize: 10 }} angle={-20} height={60} />
                        <YAxis tick={{ fontSize: 11 }} />
                        <Tooltip />
                        <Bar dataKey="cantidad" fill="#2bbcee" radius={[4, 4, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  ) : <EmptyState title="Sin datos" />}
                </CardContent>
              </Card>

              <Card>
                <CardContent className="p-5">
                  <h3 className="font-bold text-accent mb-4">Incidentes por Tipo</h3>
                  {tiposCount.length > 0 ? (
                    <ResponsiveContainer width="100%" height={300}>
                      <PieChart>
                        <Pie data={tiposCount} dataKey="cantidad" nameKey="nombre"
                          cx="50%" cy="50%" outerRadius={100} label={({ nombre, cantidad }) => `${nombre}: ${cantidad}`}>
                          {tiposCount.map((_: any, i: number) => (
                            <Cell key={i} fill={COLORS[i % COLORS.length]} />
                          ))}
                        </Pie>
                        <Tooltip />
                      </PieChart>
                    </ResponsiveContainer>
                  ) : <EmptyState title="Sin datos" />}
                </CardContent>
              </Card>
            </div>

            <Card>
              <CardContent className="p-5">
                <h3 className="font-bold text-accent mb-4">Distribución por Servicio</h3>
                {topServicios.length > 0 ? (
                  <ResponsiveContainer width="100%" height={350}>
                    <BarChart data={topServicios}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                      <XAxis dataKey="nombre" tick={{ fontSize: 11 }} angle={-30} height={70} />
                      <YAxis tick={{ fontSize: 11 }} />
                      <Tooltip />
                      <Bar dataKey="cantidad" fill="#d51b5d" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                ) : <EmptyState title="Sin datos" />}
              </CardContent>
            </Card>
          </div>
        )}

        {/* ===== TAB: KPIs GESTIÓN ===== */}
        {activeTab === "gestion" && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <KPICard title="Aprobaciones Pendientes" value={df.filter((d: any) => d.estado?.toLowerCase().includes("pendiente")).length} />
              <KPICard title="Servicios Afectados" value={serviciosUnicos.length} />
              <KPICard title="Terceros Involucrados" value={proveedoresCount.length} />
            </div>

            {productividad.length > 0 && (
              <Card>
                <CardContent className="p-5">
                  <h3 className="font-bold text-accent mb-4">Productividad por Analista (Casos vs MTTR)</h3>
                  <ResponsiveContainer width="100%" height={350}>
                    <ScatterChart>
                      <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                      <XAxis dataKey="Casos" name="Casos Resueltos" tick={{ fontSize: 11 }} />
                      <YAxis dataKey="MTTR" name="MTTR (min)" tick={{ fontSize: 11 }} />
                      <Tooltip cursor={{ strokeDasharray: "3 3" }} formatter={(value: any, name: any) => [name === "MTTR" ? formatMinutes(value) : value, name]} />
                      <Scatter data={productividad} fill="#d51b5d">
                        {productividad.map((entry: any, idx: number) => (
                          <Cell key={idx} fill={COLORS[idx % COLORS.length]} />
                        ))}
                      </Scatter>
                    </ScatterChart>
                  </ResponsiveContainer>
                  <div className="flex flex-wrap gap-3 mt-3 justify-center">
                    {productividad.map((p: any, i: number) => (
                      <div key={p.analista} className="flex items-center gap-1.5 text-xs">
                        <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: COLORS[i % COLORS.length] }} />
                        <span className="text-muted-foreground">{p.analista}: {p.Casos} casos, MTTR {formatMinutes(p.MTTR)}</span>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}

            {df.length > 0 && (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <Card>
                  <CardContent className="p-5">
                    <h3 className="font-bold text-accent mb-4">MTTR por Afectación</h3>
                    {(() => {
                      const afectMap: Record<string, number[]> = {};
                      cerradosConTiempo.forEach((d: any) => {
                        const key = d.afectacion || "Sin especificar";
                        if (!afectMap[key]) afectMap[key] = [];
                        afectMap[key].push(Math.max(0, (new Date(d.fecha_envio).getTime() - new Date(d.fecha_creacion).getTime()) / 60000));
                      });
                      const data = Object.entries(afectMap).map(([nombre, tiempos]) => ({
                        nombre, mttr: Math.round(tiempos.reduce((a, b) => a + b, 0) / tiempos.length)
                      }));
                      return data.length > 0 ? (
                        <ResponsiveContainer width="100%" height={250}>
                          <BarChart data={data}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                            <XAxis dataKey="nombre" tick={{ fontSize: 11 }} />
                            <YAxis tick={{ fontSize: 11 }} />
                            <Tooltip formatter={(v: any) => formatMinutes(v)} />
                            <Bar dataKey="mttr" fill="#10004F" radius={[4, 4, 0, 0]} />
                          </BarChart>
                        </ResponsiveContainer>
                      ) : <EmptyState title="Sin datos" />;
                    })()}
                  </CardContent>
                </Card>

                <Card>
                  <CardContent className="p-5">
                    <h3 className="font-bold text-accent mb-4">Estado de Comunicados</h3>
                    {(() => {
                      const estadosCount = Object.entries(
                        df.reduce((acc: any, d: any) => { acc[d.estado] = (acc[d.estado] || 0) + 1; return acc; }, {})
                      ).map(([nombre, cantidad]) => ({ nombre, cantidad }));
                      return estadosCount.length > 0 ? (
                        <ResponsiveContainer width="100%" height={250}>
                          <PieChart>
                            <Pie data={estadosCount} dataKey="cantidad" nameKey="nombre"
                              cx="50%" cy="50%" outerRadius={90} label={({ nombre, cantidad }) => `${nombre}: ${cantidad}`}>
                              {estadosCount.map((_: any, i: number) => (
                                <Cell key={i} fill={COLORS[i % COLORS.length]} />
                              ))}
                            </Pie>
                            <Tooltip />
                          </PieChart>
                        </ResponsiveContainer>
                      ) : <EmptyState title="Sin datos" />;
                    })()}
                  </CardContent>
                </Card>
              </div>
            )}
          </div>
        )}

        {/* ===== TAB: TENDENCIAS ===== */}
        {activeTab === "tendencias" && (
          <div className="space-y-6">
            <Card>
              <CardContent className="p-5">
                <h3 className="font-bold text-accent mb-4">Volumen de Eventos por Día</h3>
                {tendencia.length > 0 ? (
                  <ResponsiveContainer width="100%" height={300}>
                    <BarChart data={tendencia}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                      <XAxis dataKey="dia" tick={{ fontSize: 10 }} tickFormatter={v => v?.slice(5) || ""} />
                      <YAxis tick={{ fontSize: 11 }} />
                      <Tooltip />
                      <Bar dataKey="cantidad" fill="#10004F" radius={[2, 2, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                ) : <EmptyState title="Sin datos" />}
              </CardContent>
            </Card>

            <Card>
              <CardContent className="p-5">
                <h3 className="font-bold text-accent mb-4">Downtime Total por Día</h3>
                {(() => {
                  const downtimeDia = cerradosConTiempo.reduce((acc: any, d: any) => {
                    const dia = d.fecha_creacion?.slice(0, 10);
                    if (!dia) return acc;
                    const minutos = Math.max(0, (new Date(d.fecha_envio).getTime() - new Date(d.fecha_creacion).getTime()) / 60000);
                    acc[dia] = (acc[dia] || 0) + minutos;
                    return acc;
                  }, {});
                  const data = Object.entries(downtimeDia).sort(([a], [b]) => a.localeCompare(b))
                    .map(([dia, downtime]) => ({ dia, downtime: Math.round(downtime as number) }));
                  return data.length > 0 ? (
                    <ResponsiveContainer width="100%" height={300}>
                      <AreaChart data={data}>
                        <defs><linearGradient id="colorDt" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#d51b5d" stopOpacity={0.3} />
                          <stop offset="95%" stopColor="#d51b5d" stopOpacity={0} />
                        </linearGradient></defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                        <XAxis dataKey="dia" tick={{ fontSize: 10 }} tickFormatter={v => v?.slice(5) || ""} />
                        <YAxis tick={{ fontSize: 11 }} />
                        <Tooltip formatter={(v: any) => formatMinutes(v)} />
                        <Area type="monotone" dataKey="downtime" stroke="#d51b5d" fill="url(#colorDt)" strokeWidth={2} />
                      </AreaChart>
                    </ResponsiveContainer>
                  ) : <EmptyState title="Sin datos de cierre" />;
                })()}
              </CardContent>
            </Card>
          </div>
        )}

        {/* ===== TAB: HORARIO CRÍTICO ===== */}
        {activeTab === "horario" && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <Card>
                <CardContent className="p-5">
                  <h3 className="font-bold text-accent mb-4">Incidentes por Hora del Día</h3>
                  <ResponsiveContainer width="100%" height={300}>
                    <BarChart data={horaDist}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                      <XAxis dataKey="hora" tick={{ fontSize: 11 }}
                        tickFormatter={v => `${String(v).padStart(2, "0")}:00`} />
                      <YAxis tick={{ fontSize: 11 }} />
                      <Tooltip labelFormatter={(v: any) => `${String(v).padStart(2, "0")}:00 - ${String(v).padStart(2, "0")}:59`} />
                      <Bar dataKey="cantidad" fill="#d51b5d" radius={[2, 2, 0, 0]}>
                        {horaDist.map((entry: any, idx: number) => (
                          <Cell key={idx} fill={entry.cantidad > Math.max(...horaDist.map(h => h.cantidad)) * 0.7 ? "#d51b5d" :
                            entry.cantidad > Math.max(...horaDist.map(h => h.cantidad)) * 0.4 ? "#ffb74d" : "#2bbcee"} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </CardContent>
              </Card>

              <Card>
                <CardContent className="p-5">
                  <h3 className="font-bold text-accent mb-4">Incidentes por Día de la Semana</h3>
                  <ResponsiveContainer width="100%" height={300}>
                    <BarChart data={diaDist}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                      <XAxis dataKey="nombre" tick={{ fontSize: 11 }} />
                      <YAxis tick={{ fontSize: 11 }} />
                      <Tooltip />
                      <Bar dataKey="cantidad" fill="#2bbcee" radius={[4, 4, 0, 0]}>
                        {diaDist.map((entry: any, idx: number) => (
                          <Cell key={idx} fill={idx >= 5 ? "#d51b5d" : "#2bbcee"} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </CardContent>
              </Card>
            </div>

            <Card>
              <CardContent className="p-5">
                <h3 className="font-bold text-accent mb-4">Mapa de Calor: Servicio × Mes</h3>
                {(() => {
                  const heatData = df.reduce((acc: any, d: any) => {
                    if (!d.fecha_creacion || !d.servicio) return acc;
                    const mes = d.fecha_creacion.slice(0, 7);
                    const key = `${d.servicio}|${mes}`;
                    acc[key] = (acc[key] || 0) + 1;
                    return acc;
                  }, {});
                  const entries = Object.entries(heatData);
                  const maxVal = Math.max(...entries.map(([, v]) => v as number), 1);
                  const data = entries.map(([k, v]) => {
                    const [servicio, mes] = k.split("|");
                    return { servicio, mes, value: v as number, intensity: (v as number) / maxVal };
                  });
                  const meses = [...new Set(data.map(d => d.mes))].sort();
                  const servicios = [...new Set(data.map(d => d.servicio))].sort();
                  return data.length > 0 ? (
                    <div className="overflow-x-auto">
                      <table className="w-full text-xs">
                        <thead>
                          <tr>
                            <th className="text-left p-1.5 text-muted-foreground font-semibold">Servicio</th>
                            {meses.map(m => <th key={m} className="p-1.5 text-center text-muted-foreground font-semibold">{m}</th>)}
                          </tr>
                        </thead>
                        <tbody>
                          {servicios.map(s => (
                            <tr key={s}>
                              <td className="p-1.5 text-muted-foreground whitespace-nowrap">{s}</td>
                              {meses.map(m => {
                                const cell = data.find(d => d.servicio === s && d.mes === m);
                                const intensity = cell?.intensity || 0;
                                const bg = intensity > 0.7 ? "#d51b5d" : intensity > 0.4 ? "#ffb74d" : intensity > 0 ? "#2bbcee" : "#f8f9fa";
                                const textColor = intensity > 0.4 ? "#fff" : "#10004F";
                                return (
                                  <td key={m} className="p-1.5 text-center font-medium rounded" style={{ backgroundColor: bg, color: textColor }}>
                                    {cell?.value || "-"}
                                  </td>
                                );
                              })}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : <EmptyState title="Sin datos" />;
                })()}
              </CardContent>
            </Card>
          </div>
        )}

        {/* ===== TAB: DATOS DETALLADOS ===== */}
        {activeTab === "datos" && (
          <Card>
            <CardContent className="p-5">
              <h3 className="font-bold text-accent mb-4">Auditoría Detallada ({df.length} registros)</h3>
              <DataTable columns={[
                { key: "consecutivo_num", header: "ID" },
                { key: "servicio", header: "Servicio" },
                { key: "plataforma", header: "Plataforma" },
                { key: "tipo", header: "Tipo" },
                { key: "estado", header: "Estado", render: (item: any) => (
                  <Badge variant={item.estado === "Cerrado" ? "success" : item.estado?.toLowerCase().includes("pendiente") ? "warning" : "info"}>{item.estado}</Badge>
                )},
                { key: "afectacion", header: "Afectación", render: (item: any) => (
                  <Badge variant={item.afectacion === "Afecta Disponibilidad" ? "danger" : item.afectacion === "Afectación Parcial" ? "warning" : "info"}>{item.afectacion || "N/A"}</Badge>
                )},
                { key: "fecha_creacion", header: "Creación", render: (item: any) => formatDate(item.fecha_creacion) },
                { key: "fecha_envio", header: "Cierre", render: (item: any) => formatDate(item.fecha_envio) },
                { key: "escalado", header: "SLA", render: (item: any) => item.escalado ? <Badge variant="danger">Incumplido</Badge> : <Badge variant="success">Cumplido</Badge> },
                { key: "analista", header: "Analista" },
              ]} data={df.slice(0, 500)} />
              {df.length > 500 && (
                <p className="text-xs text-muted-foreground mt-2">Mostrando 500 de {df.length} registros. Usa filtros para acotar.</p>
              )}
            </CardContent>
          </Card>
        )}

        {/* ===== TAB: EXPORTACIÓN ===== */}
        {activeTab === "exportar" && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Card>
              <CardContent className="p-6 space-y-4">
                <div className="flex items-center gap-3">
                  <FileSpreadsheet size={24} className="text-green-600" />
                  <div>
                    <h3 className="font-bold text-accent">Exportar a CSV</h3>
                    <p className="text-xs text-muted-foreground">
                      {hayFiltros
                        ? `${df.length} registros filtrados`
                        : `${total} registros históricos`
                      }
                    </p>
                  </div>
                </div>
                <Button onClick={exportarExcel} disabled={exportLoading} className="w-full gap-2">
                  <Download size={16} /> {exportLoading ? "Generando..." : "Descargar CSV"}
                </Button>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="p-6 space-y-4">
                <div className="flex items-center gap-3">
                  <Eye size={24} className="text-primary" />
                  <div>
                    <h3 className="font-bold text-accent">Resumen del Período</h3>
                    <p className="text-xs text-muted-foreground">Métricas clave del conjunto de datos actual</p>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div className="bg-muted/30 p-3 rounded-xl">
                    <p className="text-xs text-muted-foreground">Total</p>
                    <p className="font-bold text-accent text-lg">{total}</p>
                  </div>
                  <div className="bg-muted/30 p-3 rounded-xl">
                    <p className="text-xs text-muted-foreground">Cerrados</p>
                    <p className="font-bold text-accent text-lg">{cerrados} <span className="text-xs font-normal text-muted-foreground">({pctCierre}%)</span></p>
                  </div>
                  <div className="bg-muted/30 p-3 rounded-xl">
                    <p className="text-xs text-muted-foreground">MTTR</p>
                    <p className="font-bold text-accent text-lg">{formatMinutes(mttr)}</p>
                  </div>
                  <div className="bg-muted/30 p-3 rounded-xl">
                    <p className="text-xs text-muted-foreground">SLA</p>
                    <p className="font-bold text-accent text-lg">{slaPct}%</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        )}
      </div>
    </AppShell>
  );
}
