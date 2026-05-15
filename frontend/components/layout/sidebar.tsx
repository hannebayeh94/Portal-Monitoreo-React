"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth";
import {
  LayoutDashboard, ShieldCheck, FileEdit, CheckSquare,
  Wrench, History, BarChart3, Settings, LogOut,
  Activity, ChevronLeft, ChevronRight
} from "lucide-react";
import { useState } from "react";

export function Sidebar() {
  const pathname = usePathname();
  const { user, logout, tienePermiso } = useAuth();
  const [collapsed, setCollapsed] = useState(false);

  const iniciales = user ? `${user.nombre[0]}${user.apellido[0]}`.toUpperCase() : "??";

  const menuItems = [
    { section: "General", items: [
      { href: "/dashboard", label: "Centro Operativo", icon: LayoutDashboard },
    ]},
    { section: "Operaciones", items: [
      ...(tienePermiso("ver_aprobaciones") || tienePermiso("puede_aprobar")
        ? [{ href: "/autorizaciones", label: "Autorizaciones", icon: ShieldCheck }]
        : []),
      ...(tienePermiso("ver_apertura")
        ? [{ href: "/incidencias/nueva", label: "Nueva Novedad", icon: FileEdit }]
        : []),
      ...(tienePermiso("ver_cierre")
        ? [{ href: "/incidencias/cerrar", label: "Cerrar Novedad", icon: CheckSquare }]
        : []),
      ...(tienePermiso("ver_mantenimiento")
        ? [{ href: "/mantenimientos", label: "Mantenimientos", icon: Wrench }]
        : []),
      ...(tienePermiso("ver_edicion")
        ? [{ href: "/historial", label: "Historial", icon: History }]
        : []),
    ]},
    { section: "Administración", items: [
      ...(tienePermiso("ver_reportes")
        ? [{ href: "/reportes", label: "Informes", icon: BarChart3 }]
        : []),
      ...(tienePermiso("ver_admin")
        ? [{ href: "/admin", label: "Administración", icon: Settings }]
        : []),
    ]},
  ].filter(section => section.items.length > 0);

  return (
    <aside className={cn(
      "h-screen sticky top-0 flex flex-col bg-accent text-white transition-all duration-300 z-50",
      collapsed ? "w-16" : "w-64"
    )}>
      <div className={cn("flex items-center gap-3 px-4 h-16 border-b border-white/10", collapsed && "justify-center")}>
        {!collapsed && (
          <div className="flex items-center gap-2">
            <Activity className="text-secondary" size={24} />
            <span className="font-bold text-base">SOC Portal</span>
          </div>
        )}
        {collapsed && <Activity className="text-secondary" size={24} />}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="ml-auto text-white/60 hover:text-white transition-colors"
        >
          {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>
      </div>

      <div className={cn("px-3 py-4 border-b border-white/10", collapsed && "flex justify-center")}>
        <div className={cn("flex items-center gap-3", collapsed && "flex-col")}>
          <div className="w-9 h-9 rounded-full bg-primary flex items-center justify-center text-sm font-bold shrink-0">
            {iniciales}
          </div>
          {!collapsed && (
            <div className="min-w-0">
              <p className="text-sm font-semibold truncate">{user?.nombre} {user?.apellido}</p>
              <p className="text-xs text-white/60 uppercase tracking-wider">{user?.rol}</p>
            </div>
          )}
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto py-3">
        {menuItems.map((section) => (
          <div key={section.section} className="mb-2">
            {!collapsed && (
              <p className="px-4 py-1 text-xs font-semibold text-white/40 uppercase tracking-widest">
                {section.section}
              </p>
            )}
            {section.items.map((item) => {
              const Icon = item.icon;
              const isActive = pathname.startsWith(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "flex items-center gap-3 mx-2 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200",
                    collapsed && "justify-center mx-1",
                    isActive
                      ? "bg-primary text-white shadow-lg shadow-primary/30"
                      : "text-white/70 hover:text-white hover:bg-white/10"
                  )}
                  title={collapsed ? item.label : undefined}
                >
                  <Icon size={20} />
                  {!collapsed && <span>{item.label}</span>}
                </Link>
              );
            })}
          </div>
        ))}
      </nav>

      <div className={cn("p-3 border-t border-white/10", collapsed && "flex justify-center")}>
        <button
          onClick={logout}
          className={cn(
            "flex items-center gap-3 w-full px-3 py-2.5 rounded-xl text-sm font-medium text-white/60 hover:text-red-300 hover:bg-white/10 transition-all duration-200",
            collapsed && "justify-center"
          )}
          title={collapsed ? "Cerrar Sesión" : undefined}
        >
          <LogOut size={20} />
          {!collapsed && <span>Cerrar Sesión</span>}
        </button>
      </div>
    </aside>
  );
}
