## Context

`apps/web/src/features/session/SessionProvider.tsx` ya expone el contrato de sesión (`status`, `profile`, `authenticate`, `switchRole`) que consume `RequireSession`; el único mecanismo de `authenticate` hoy es `devTokenFor(role)` (ver `devTokens.ts`), disponible solo cuando `import.meta.env.DEV`. `apps/web/src/shared/api/client.ts` ya separa la adjunción del token (`setApiAuthToken`) del resto del cliente HTTP, así que el nuevo flujo solo necesita producir un `access_token` y llamar a esa función existente — no hace falta tocar `client.ts`. En el backend, `app/identity/auth.py` ya valida cualquier JWT HS256 que cumpla issuer/audience/`exp`/`sub` de Supabase; un token real de Supabase Auth ya cumple ese contrato hoy, así que el backend no cambia. Ver `proposal.md - Why` para la motivación.

## Goals / Non-Goals

**Goals:**
- Login real utilizable en un build de producción (`import.meta.env.PROD`), sin depender de tokens precodificados.
- Sesión que sobrevive a un refresh de página y se renueva sola.
- Cambio aislado al frontend; cero cambios de contrato en la API.

**Non-Goals:**
- Login con contraseña, OAuth social o SSO — solo magic link/OTP por email en esta change.
- Gestión de invitaciones o alta de nuevos perfiles/membresías (ya cubierto por `app/identity`, fuera de alcance aquí).
- Personalización del email del magic link (plantilla/branding) — configuración del proyecto Supabase, no código de la aplicación.
- Eliminar o modificar el selector de identidades de desarrollo existente.

## Decisions

**Cliente: `@supabase/supabase-js` en vez de llamadas REST manuales al Auth API.**
Es el cliente first-party de Supabase, ya usado como plataforma (Postgres/RLS) en el resto del proyecto; maneja el intercambio del magic link, el almacenamiento de sesión y el auto-refresh del token sin reimplementar ese protocolo a mano. Alternativa descartada: `fetch` directo contra `GOTRUE_URL` — más control pero reimplementa refresh/storage que el SDK ya resuelve, sin beneficio dado que no hay restricción de bundle size conocida.

**Un solo cliente Supabase, creado en `apps/web/src/features/session/supabaseClient.ts`.**
Se inicializa una vez con `VITE_SUPABASE_URL`/`VITE_SUPABASE_ANON_KEY` (nuevas env vars, mismo patrón que `VITE_API_URL`). `SessionProvider` se suscribe a `supabase.auth.onAuthStateChange` en vez de manejar su propio timer de expiración: el SDK ya dispara ese callback en login, logout y refresh.

**Adjunción del token reutiliza `setApiAuthToken` sin tocar `client.ts`.**
En cada evento de `onAuthStateChange`, el listener llama `setApiAuthToken(session?.access_token ?? null)` y dispara el mismo `GET /api/v1/me` que ya usa el flujo de identidades de dev para construir el `SessionProfile` — la lógica de `toProfile(me)` no cambia.

**Convivencia vía rama en `import.meta.env.DEV`/`PROD`, no un flag nuevo.**
`import.meta.env.DEV`/`PROD` ya son estáticos y ya gobiernan `devTokenFor`/`availableDevRoles` (se eliminan en build de producción por dead-code elimination). La pantalla de login (hoy `SessionMissingState`) se extiende para mostrar siempre el formulario de magic link, y mostrar además los accesos de identidad de dev solo cuando `availableDevRoles().length > 0` (ya es la condición actual) — sin introducir una env var de feature flag adicional.

**Alcance del token: `access_token` de Supabase se usa tal cual, sin sesión propia del backend.**
El backend no emite ni almacena tokens (`app/identity/auth.py` es puramente un verificador). No se introduce un endpoint de "exchange" ni cookies de sesión del lado del servidor — mismo modelo que el flujo de dev tokens ya usa (bearer token en cada request).

## Risks / Trade-offs

- [El proyecto Supabase debe tener el magic link/OTP habilitado y las redirect URLs de la app en su allowlist] → Verificación operativa (dashboard de Supabase), no de código; documentar el requisito en `tasks.md` para no descubrirlo recién en producción.
- [`onAuthStateChange` puede disparar un evento `INITIAL_SESSION` antes de que `apiFetch('/api/v1/me')` resuelva, produciendo un parpadeo de estado] → Mismo patrón de `status: 'initializing'` que ya maneja `RequireSession`; el listener solo transiciona a `authenticated` tras el `GET /me` exitoso, igual que `authenticate()` hoy.
- [Un usuario con sesión de Supabase válida pero sin membresía en ninguna marca] → Ya cubierto por el backend (`GET /me` con memberships vacío); la pantalla ya maneja `profile.membership` nulo aguas abajo — sin cambio de contrato necesario aquí.

## Migration Plan

1. Configurar el proyecto Supabase (dashboard): habilitar magic link, registrar las redirect URLs de dev y producción.
2. Añadir `VITE_SUPABASE_URL`/`VITE_SUPABASE_ANON_KEY` a `apps/web/.env.example` y a los entornos reales (dev local, producción) — nunca commitear el valor real.
3. Instalar `@supabase/supabase-js` (`npm install --workspace @content-suite/web`, versión resuelta vía Context7 según `AGENTS.md` §12).
4. Implementar `supabaseClient.ts` y extender `SessionProvider`/`SessionMissingState` como se describe arriba.
5. Verificar manualmente el flujo end-to-end contra el proyecto Supabase real: solicitar magic link, confirmar, recargar página, cerrar sesión.
6. Rollback: revertir el commit del frontend; el backend no tiene estado que revertir (no cambia).

## Open Questions

(ninguna — las decisiones de alcance de esta change quedan resueltas arriba)
