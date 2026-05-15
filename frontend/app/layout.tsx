import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/lib/auth";
import { Toaster } from "sonner";

export const metadata: Metadata = {
  title: "Portal de Comunicados TI",
  description: "Sistema de gesti\u00f3n de comunicados de novedades TI",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es" suppressHydrationWarning>
      <body>
        <AuthProvider>
          {children}
          <Toaster
            position="top-right"
            richColors
            closeButton
            toastOptions={{
              style: { borderRadius: "12px", padding: "16px" },
            }}
          />
        </AuthProvider>
      </body>
    </html>
  );
}
