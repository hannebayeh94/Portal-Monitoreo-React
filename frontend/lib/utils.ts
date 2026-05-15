import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return "-";
  const d = new Date(dateStr);
  return d.toLocaleDateString("es-CO", {
    day: "2-digit", month: "short", year: "numeric",
    hour: "2-digit", minute: "2-digit"
  });
}

export function formatFechaEs(date: Date): string {
  const meses = ["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dec"];
  return `${String(date.getDate()).padStart(2,"0")} ${meses[date.getMonth()]} ${date.getFullYear()} - ${date.toLocaleTimeString("es-CO", {hour:"2-digit", minute:"2-digit"})} (COT)`;
}

export function calcularEstadoSla(fechaCreacion: string, slaHoras: number): { label: string; color: string } {
  const ahora = new Date();
  const inicio = new Date(fechaCreacion);
  const horas = (ahora.getTime() - inicio.getTime()) / (1000 * 3600);
  if (horas >= slaHoras) return { label: "Incumplido", color: "text-red-600 bg-red-50" };
  if (horas >= slaHoras * 0.75) return { label: "En Riesgo", color: "text-amber-600 bg-amber-50" };
  return { label: "A tiempo", color: "text-green-600 bg-green-50" };
}

export function calcularTiempoTranscurrido(segundos: number): string {
  if (segundos < 60) return "Menos de 1 minuto";
  const h = Math.floor(segundos / 3600);
  const m = Math.floor((segundos % 3600) / 60);
  const partes: string[] = [];
  if (h > 0) partes.push(`${h} hora${h !== 1 ? "s" : ""}`);
  if (m > 0) partes.push(`${m} minuto${m !== 1 ? "s" : ""}`);
  return partes.join(", ");
}

export function esCorreoValido(correo: string): boolean {
  return /^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$/.test(correo);
}
