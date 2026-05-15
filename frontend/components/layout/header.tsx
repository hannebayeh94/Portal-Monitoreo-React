"use client";

import { useAuth } from "@/lib/auth";

export function Header() {
  const { user } = useAuth();

  return (
    <header className="h-16 border-b bg-white/80 backdrop-blur-sm flex items-center justify-between px-6 sticky top-0 z-40">
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
          <span className="text-sm text-muted-foreground">Sistema Operativo</span>
        </div>
      </div>
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <span className="hidden sm:inline">
            {user?.nombre} {user?.apellido}
          </span>
          <span className="px-2 py-0.5 rounded-full bg-primary-light text-primary text-xs font-semibold">
            {user?.rol}
          </span>
        </div>
      </div>
    </header>
  );
}
