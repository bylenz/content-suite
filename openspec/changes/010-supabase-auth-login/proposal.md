## Why

La pantalla de login actual solo ofrece un selector de identidades de desarrollo (`Entrar como Creator / Content Reviewer / Visual Compliance Reviewer`), respaldado por tokens leídos de `apps/web/.env.development.local` que expiran a los 15 minutos y solo existen cuando `import.meta.env.DEV` es verdadero. El propio texto de la pantalla lo declara: "La autenticación completa llega con Supabase Auth en una change posterior." Sin un flujo de login real, la aplicación no tiene ninguna forma de autenticar un usuario en un build de producción (`import.meta.env.DEV` es falso ahí, y la pantalla de login queda sin ninguna acción disponible), lo que bloquea cualquier despliegue fuera de la máquina de un desarrollador.

## What Changes

- Añade un login real vía Supabase Auth (magic link / OTP por email) como único camino de entrada en builds de producción.
- El frontend usa `@supabase/supabase-js` para iniciar el magic link, recibir la sesión (access + refresh token) y adjuntar el `access_token` a cada request de la API — mismo contrato JWT que `app/identity/auth.py` ya valida (HS256, issuer/audience de Supabase, claims `exp`/`sub` obligatorios); la API no cambia.
- `SessionProvider` se extiende para detectar una sesión de Supabase existente al montar (recarga de página), refrescar el token antes de que expire, y exponer un cierre de sesión explícito.
- El selector de identidades de desarrollo (`devTokens.ts`, `RequireSession`, `SessionMissingState`) se conserva sin cambios de comportamiento y sigue existiendo exclusivamente en builds `DEV`, como atajo de desarrollo local que coexiste con el login real — no se elimina ni se reemplaza.
- **BREAKING**: ninguno. La API ya exige un JWT válido de Supabase (`auth_jwt_secret`/`auth_jwt_issuer` configurados); el cambio es enteramente de frontend y aditivo.

## Capabilities

### New Capabilities
- `session-auth`: login real con Supabase Auth (magic link) para producción, persistencia y refresh de sesión en el frontend, y cierre de sesión explícito, coexistiendo con el selector de identidades de desarrollo existente (`DEV` only).

### Modified Capabilities
(ninguna — el contrato de autenticación del backend, ya cubierto por `foundation`, no cambia: sigue exigiendo un JWT Supabase válido y sigue sin exponer perfil sin él)

## Impact

- Frontend: `apps/web/src/features/session/*` (nuevo cliente Supabase, `SessionProvider`, `RequireSession`, `session-context`), nueva pantalla de login de producción, `apps/web/package.json` (nueva dependencia `@supabase/supabase-js`), nuevas variables `VITE_SUPABASE_URL` / `VITE_SUPABASE_ANON_KEY` en `apps/web/.env.example`.
- Backend: sin cambios de contrato ni de código; `CONTENT_SUITE_AUTH_JWT_SECRET`/`ISSUER`/`AUDIENCE` ya están configurados contra el proyecto Supabase real.
- Dependencias: `@supabase/supabase-js` (frontend, vía Context7 antes de fijar versión, según `AGENTS.md` §12).
