const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface FetchOptions extends RequestInit {
  skipAuth?: boolean;
}

async function request<T>(path: string, options: FetchOptions = {}): Promise<T> {
  const { skipAuth, ...fetchOpts } = options;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(fetchOpts.headers as Record<string, string>),
  };

  if (!skipAuth) {
    const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null;
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, { ...fetchOpts, headers });

  if (res.status === 401 && !skipAuth) {
    if (typeof window !== "undefined") {
      localStorage.removeItem("access_token");
      localStorage.removeItem("user_info");
      localStorage.removeItem("user_permisos");
      localStorage.removeItem("user_servicios_rest");
      window.location.href = "/login";
    }
    throw new Error("No autorizado");
  }

  if (res.status === 403) {
    const detail = await res.json().catch(() => ({ detail: "Acceso denegado" }));
    throw new Error(detail.detail || "Acceso denegado por permisos insuficientes");
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Error desconocido" }));
    throw new Error(err.detail || `Error ${res.status}`);
  }

  return res.json();
}

export const api = {
  get: <T>(path: string, options?: FetchOptions) => request<T>(path, options),
  post: <T>(path: string, data?: unknown, options?: FetchOptions) =>
    request<T>(path, { method: "POST", body: data ? JSON.stringify(data) : undefined, ...options }),
  put: <T>(path: string, data?: unknown, options?: FetchOptions) =>
    request<T>(path, { method: "PUT", body: data ? JSON.stringify(data) : undefined, ...options }),
  delete: <T>(path: string, options?: FetchOptions) => request<T>(path, { method: "DELETE", ...options }),
};

export default api;
