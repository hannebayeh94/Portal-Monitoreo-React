"use client";

import { createContext, useContext, useState, useEffect, ReactNode, useCallback } from "react";
import api from "./api-client";

interface User {
  id: number;
  nombre: string;
  apellido: string;
  correo: string;
  rol: string;
}

interface Permisos {
  [key: string]: boolean;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  permisos: Permisos;
  serviciosRestringidos: number[];
  login: (correo: string, password: string) => Promise<void>;
  logout: () => void;
  isAuthenticated: boolean;
  isLoading: boolean;
  tienePermiso: (permiso: string) => boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [permisos, setPermisos] = useState<Permisos>({});
  const [serviciosRestringidos, setServiciosRestringidos] = useState<number[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const loadSession = useCallback(async () => {
    const savedToken = localStorage.getItem("access_token");
    const savedUser = localStorage.getItem("user_info");
    const savedPermisos = localStorage.getItem("user_permisos");
    const savedServicios = localStorage.getItem("user_servicios_rest");
    if (savedToken && savedUser) {
      setToken(savedToken);
      setUser(JSON.parse(savedUser));
      setPermisos(savedPermisos ? JSON.parse(savedPermisos) : {});
      setServiciosRestringidos(savedServicios ? JSON.parse(savedServicios) : []);

      try {
        const res: any = await api.get("/auth/me", { skipAuth: false } as any);
        if (res.permisos) {
          setPermisos(res.permisos);
          localStorage.setItem("user_permisos", JSON.stringify(res.permisos));
        }
        if (res.servicios_restringidos) {
          setServiciosRestringidos(res.servicios_restringidos);
          localStorage.setItem("user_servicios_rest", JSON.stringify(res.servicios_restringidos));
        }
      } catch {
        // Token might be expired; stay with cached data
      }
    }
    setIsLoading(false);
  }, []);

  useEffect(() => {
    loadSession();
  }, [loadSession]);

  const login = async (correo: string, password: string) => {
    const res: any = await api.post("/auth/login", { correo, password });
    localStorage.setItem("access_token", res.access_token);
    localStorage.setItem("user_info", JSON.stringify(res.user));
    localStorage.setItem("user_permisos", JSON.stringify(res.permisos || {}));
    localStorage.setItem("user_servicios_rest", JSON.stringify(res.servicios_restringidos || []));
    setToken(res.access_token);
    setUser(res.user);
    setPermisos(res.permisos || {});
    setServiciosRestringidos(res.servicios_restringidos || []);
  };

  const logout = () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("user_info");
    localStorage.removeItem("user_permisos");
    localStorage.removeItem("user_servicios_rest");
    setToken(null);
    setUser(null);
    setPermisos({});
    setServiciosRestringidos([]);
  };

  const tienePermiso = (permiso: string): boolean => {
    return permisos[permiso] == true;
  };

  return (
    <AuthContext.Provider value={{
      user, token, permisos, serviciosRestringidos,
      login, logout, isAuthenticated: !!token, isLoading, tienePermiso
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth debe usarse dentro de AuthProvider");
  return ctx;
}
