# INFORME DE ANÁLISIS Y MEJORAS — PORTAL DE COMUNICADOS TI

## 1. Verificación de Integridad y Lógica

### Problemas detectados en el código migrado (Backend FastAPI):

| Archivo | Problema | Gravedad |
|---------|----------|----------|
| `backend/app/api/deps.py` | `get_current_user` no validaba que el usuario estuviera activo (`estado = TRUE`) | **Crítica** — permitía acceso a usuarios desactivados |
| `backend/app/api/deps.py` | No existía verificación de roles/permisos para ningún endpoint | **Crítica** — cualquier rol accedía a todo |
| `backend/app/api/routes/admin.py` | Todos los endpoints usaban `get_current_user` sin verificar rol administrador | **Crítica** — roles no administradores podían modificar configuración |
| `backend/app/api/routes/auth.py` | Endpoint `/me` usaba query param `token` en vez de `Authorization: Bearer` | **Alta** — inconsistente con el resto de endpoints |
| `backend/app/services/__init__.py` | `formatear_fecha_es` solo aceptaba string, no (date, time) como el original | **Media** — pérdida de funcionalidad |
| `backend/app/services/__init__.py` | `calcular_tiempo_transcurrido` esperaba segundos, no objetos datetime | **Media** — interfaz incompatible con V35.py |
| `backend/app/services/__init__.py` | Faltaban funciones: `calcular_estado_sla()`, `obtener_correos_cc()` | **Media** — funcionalidad SLA incompleta |
| `backend/app/services/email_service.py` | No integraba `correos_cc` (correos internos en CC) para comunicaciones externas | **Alta** — los correos externos no incluían copia interna |
| `backend/app/services/sla_service.py` | No enviaba alertas de seguridad para acciones críticas (ADMIN_CRITICO) | **Media** — pérdida de auditoría de seguridad |
| `backend/app/api/routes/comunicados.py` | No existían endpoints: SLA check, preview reglas, estadísticas sidebar | **Alta** — frontend sin datos para KPIs |
| `backend/app/api/routes/comunicados.py` | Endpoint `pending-approval` sin verificación de permiso `puede_aprobar` | **Alta** — cualquier rol podía ver aprobaciones |

### Problemas detectados en el Frontend (Next.js/React):

| Archivo | Problema | Gravedad |
|---------|----------|----------|
| `frontend/lib/auth.tsx` | No almacenaba permisos del usuario, solo info básica | **Crítica** — sidecar sin control de acceso |
| `frontend/components/layout/sidebar.tsx` | Mostraba TODAS las opciones del menú a cualquier usuario autenticado | **Crítica** — usuarios de monitoreo veían admin |
| `frontend/lib/api-client.ts` | No manejaba error 403 (Forbidden), solo 401 | **Media** — sin feedback de permisos insuficientes |

---

## 2. Funcionalidades Ausentes vs V35.py

### Completamente implementadas en el frontend migrado:
- ✅ Dashboard con KPIs, gráficos, monitor SLA
- ✅ Autenticación con login/registro
- ✅ Administración completa (11 secciones: SLA, reglas, roles, servicios, terceros, vínculos, correos, usuarios, plantillas, auditoría)
- ✅ Autorizaciones (aprobar/rechazar)
- ✅ Historial con edición y reenvío
- ✅ Apertura de novedad (asistente 3 pasos)
- ✅ Cierre de novedad
- ✅ Mantenimientos (programar + finalizar)
- ✅ Reportes con gráficos

### Funcionalidades FALTANTES que se agregaron:
- 🔧 **Sistema de permisos backend**: `get_permisos_usuario()`, `require_permiso()`, `require_admin()` en `deps.py`
- 🔧 **Retorno de permisos en login**: El endpoint `/auth/login` ahora devuelve `permisos` y `servicios_restringidos`
- 🔧 **Endpoint `/auth/me` corregido**: Usa `Authorization: Bearer` correctamente
- 🔧 **Verificación de estado activo**: `get_current_user()` ahora valida `user["estado"]`
- 🔧 **Endpoints SLA**: `/comunicados/sla-check`, `/comunicados/estadisticas-sidebar`, `/comunicados/config-sla`
- 🔧 **Endpoints de reglas**: `/comunicados/apertura/regla-preview`, `/comunicados/cierre/regla-preview`, `/comunicados/mantenimiento/regla-preview`
- 🔧 **Alertas de seguridad**: `sla_service.py` ahora notifica al correo de seguridad sobre acciones críticas
- 🔧 **Correos CC**: `email_service.py` integra lista de correos internos en CC
- 🔧 **Sidebar con permisos**: Filtra opciones según `tienePermiso()`
- 🔧 **AuthContext con permisos**: Almacena `permisos`, `serviciosRestringidos` y expone `tienePermiso()`

---

## 3. Validación de Roles y Permisos — Implementación

### Backend (`deps.py`)

Se implementó un sistema de control de acceso basado en roles (RBAC) con:

```python
# Permisos granular por rol (desde BD tabla rol_permisos):
- ver_aprobaciones   -> Bandeja de aprobaciones
- ver_apertura       -> Nueva novedad
- ver_cierre         -> Cerrar novedad
- ver_mantenimiento  -> Mantenimientos
- ver_edicion        -> Historial y edición
- ver_reportes       -> Informes
- ver_admin          -> Panel administración
- puede_aprobar      -> Capacidad de aprobar
- ver_solo_propios   -> Ver solo casos propios
- exige_aprobacion   -> Envíos requieren aprobación

# Dependencias por permiso:
require_admin(user, db)     -> Verifica ver_admin = True
require_permiso(permiso)     -> Verifica permiso específico

# Fallback por rol si no hay registro en BD:
- Administrador -> todos los permisos
- Líder         -> sin admin, con aprobar
- Otros         -> solo apertura/cierre/mantenimiento, con exigencia de aprobación
```

### Backend (`admin.py`)

Todos los endpoints de administración ahora usan `Depends(require_admin)`:
- CRUD de reglas, servicios, terceros, plantillas, usuarios, roles, correos
- Cada modificación registra auditoría con `ADMIN_REGLAS`, `ADMIN_RBAC`, etc.

### Frontend (`sidebar.tsx`)

Ahora filita dinámicamente:
```typescript
const menuItems = [
  { section: "Operaciones", items: [
    ...(tienePermiso("ver_aprobaciones") ? [{ href: "/autorizaciones", ... }] : []),
    ...(tienePermiso("ver_apertura")     ? [{ href: "/incidencias/nueva", ... }] : []),
    ...(tienePermiso("ver_cierre")       ? [{ href: "/incidencias/cerrar", ... }] : []),
    ...(tienePermiso("ver_mantenimiento")? [{ href: "/mantenimientos", ... }] : []),
    ...(tienePermiso("ver_edicion")      ? [{ href: "/historial", ... }] : []),
  ]},
  ...
]
```

### Frontend (`auth.tsx`)

```typescript
interface AuthContextType {
  permisos: Permisos;                    // Mapa clave->booleano
  serviciosRestringidos: number[];      // IDs de servicios con acceso
  tienePermiso: (permiso: string) => boolean;
}
```

---

## 4. Cambios Realizados — Resumen

### Archivos modificados en backend:

| Archivo | Cambio |
|---------|--------|
| `backend/app/api/deps.py` | Nuevo sistema RBAC con `get_permisos_usuario()`, `require_permiso()`, `require_admin()`, `get_servicios_restringidos()`. Se agregó validación de `estado`. |
| `backend/app/api/routes/auth.py` | Login retorna `permisos` + `servicios_restringidos`. `/me` usa `Authorization: Bearer`. |
| `backend/app/api/routes/admin.py` | Todos los endpoints ahora requieren `require_admin`. Se agregaron registros de auditoría en cada acción. |
| `backend/app/api/routes/comunicados.py` | Agregados endpoints: SLA check, preview reglas, estadísticas sidebar, config SLA. Protegido `pending-approval` con verificación de permisos. |
| `backend/app/services/__init__.py` | Agregadas funciones: `calcular_estado_sla()`, `obtener_correos_cc()`. Corregidas firmas de `formatear_fecha_es()` y `calcular_tiempo_transcurrido()`. |
| `backend/app/services/email_service.py` | Agregado parámetro `correos_cc` para integración de CC internos. |
| `backend/app/services/sla_service.py` | Agregadas alertas de seguridad para acciones críticas (ADMIN_CRITICO, SEGURIDAD, ADMIN_REGLAS). |

### Archivos modificados en frontend:

| Archivo | Cambio |
|---------|--------|
| `frontend/lib/auth.tsx` | Agregado almacenamiento de `permisos`, `serviciosRestringidos`, método `tienePermiso()`. Carga desde `/auth/me` al iniciar. |
| `frontend/lib/api-client.ts` | Manejo de error 403 con mensaje descriptivo. Limpieza completa de localStorage en 401. |
| `frontend/components/layout/sidebar.tsx` | Filtrado dinámico del menú según permisos. |

---

## 5. Mejoras Adicionales Sugeridas

### Corto plazo (alta prioridad):

1. **Guard por ruta en frontend**: Crear un componente `PermissionGuard` que verifique en el `AppShell` si el usuario tiene permiso para la ruta actual y redirija si no. Ejemplo:
   ```typescript
   // Mapa de rutas a permisos
   const ROUTE_PERMISSIONS = {
     "/autorizaciones": "ver_aprobaciones",
     "/incidencias/nueva": "ver_apertura",
     "/admin": "ver_admin",
     "/reportes": "ver_reportes",
   };
   ```

2. **Refresh de token**: Implementar renovación automática del JWT antes de que expire (actualmente 480 min).

3. **Logout con auditoría**: El logout actual no registra en audit_log del backend. Agregar endpoint `POST /auth/logout`.

### Mediano plazo:

4. **Helmet.js + rate limiting**: Agregar `helmet` y `slowapi` (rate limiting) en FastAPI para seguridad contra ataques de fuerza bruta en `/auth/login`.

5. **Validación Pydantic más estricta**: Agregar `EmailStr` en `LoginRequest.correo` y en todos los schemas de correo.

6. **Pruebas unitarias**: Implementar tests para:
   - `deps.py` — verificación de permisos por rol
   - `comunicados.py` — creación, cierre, aprobación
   - `admin.py` — CRUD con y sin permisos de admin

7. **Logging centralizado**: Migrar a `structlog` para logs estructurados JSON con tracing.

8. **CSRF Protection**: Agregar tokens CSRF en el frontend para mutaciones.

9. **Cifrado de secrets**: Mover `SECRET_KEY`, `SMTP_PASSWORD` a variables de entorno con cifrado en reposo (ej. Azure Key Vault / AWS Secrets Manager).

10. **Pruebas de regresión visual**: Storybook para componentes UI compartidos.

### Arquitectura:

11. **Separación de dominios**: Migrar de FastAPI monolítico a módulos por dominio (comunicados, admin, reportes) con sus propios routers y servicios.

12. **Migración a SQLAlchemy 2.0 Mapped**: Usar `mapped_column` en lugar de `Column` para tipado estático completo.

13. **WebSockets para actualizaciones en tiempo real**: Dashboard de SOC con notificaciones push cuando un SLA está por vencer.
