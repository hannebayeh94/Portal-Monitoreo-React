"use client";

import { ReactNode, useEffect } from "react";
import { Sidebar } from "./sidebar";
import { Header } from "./header";
import { useAuth } from "@/lib/auth";
import { useRouter, usePathname } from "next/navigation";

const ROUTE_PERMISSION_MAP: Record<string, string> = {
  "/autorizaciones": "ver_aprobaciones",
  "/incidencias/nueva": "ver_apertura",
  "/incidencias/cerrar": "ver_cierre",
  "/mantenimientos": "ver_mantenimiento",
  "/historial": "ver_edicion",
  "/reportes": "ver_reportes",
  "/admin": "ver_admin",
};

export function AppShell({ children }: { children: ReactNode }) {
  const { isAuthenticated, isLoading, tienePermiso } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push("/login");
      return;
    }

    const requiredPerm = Object.entries(ROUTE_PERMISSION_MAP).find(([path]) =>
      pathname.startsWith(path)
    );
    if (requiredPerm && !tienePermiso(requiredPerm[1])) {
      router.push("/dashboard");
    }
  }, [isAuthenticated, isLoading, router, pathname, tienePermiso]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
          <p className="text-sm text-muted-foreground">Cargando...</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) return null;

  const requiredPerm = Object.entries(ROUTE_PERMISSION_MAP).find(([path]) =>
    pathname.startsWith(path)
  );
  if (requiredPerm && !tienePermiso(requiredPerm[1])) return null;

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header />
        <main className="flex-1 overflow-y-auto p-6 bg-background">
          {children}
        </main>
      </div>
    </div>
  );
}
