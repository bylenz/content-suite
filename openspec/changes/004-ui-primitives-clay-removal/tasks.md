## 1. Preparación de primitives

- [x] 1.1 Verificar Context7/registry para shadcn con Vite, React 19 y Tailwind v4, inicializarlo en `apps/web` con aliases mínimos y confirmar que `components.json` no altera rutas ni configuración no relacionada.
- [x] 1.2 Añadir sólo Button, Card, Badge, Input, Textarea y Label que reemplacen patrones existentes, adaptar sus tokens/variants al diseño Content Suite y verificar imports locales sin defaults visuales genéricos.

## 2. Sustitución de Clay CSS

- [x] 2.1 Definir superficies locales equivalentes (card, deep, chip, subtle, inset, CTA y nav activa) desde la paleta canónica y verificar contraste/foco, hover de puntero fino y reduced motion.
- [x] 2.2 Migrar selectivamente controles y superficies existentes a las primitives/estilos propios, preservando Dashboard, Create/Edit Brand DNA, roles, rutas, datos y `dialog` nativo; verificar Creator/reviewer y drawer por teclado.
- [x] 2.3 Eliminar import y dependencia `claymorphism-css`, actualizar `package-lock.json` y documentación de versiones; verificar que no queda referencia mediante búsqueda del repositorio.

## 3. Verificación

- [x] 3.1 Ejecutar `npm run lint`, `npm run typecheck` y `npm run build`; resolver errores y validar que no se altera backend, migraciones ni contratos API.
- [x] 3.2 Ejecutar detector Impeccable y revisión visual 1440×900/390×844 con reduced motion, comparando las superficies aprobadas contra `starter-design/` y la captura; documentar sólo desviaciones reales.
  - Evidencia: detector Impeccable ejecutado sobre `apps/web/src` → `[]` (sin findings). Revisión visual manual en 1440×900/390×844 con Creator/reviewer y reduced motion confirmada por el usuario: el diseño migrado conserva el aprobado; sin desviaciones reales que documentar.
- [x] 3.3 Ejecutar `npx @fission-ai/openspec@latest validate 004-ui-primitives-clay-removal --strict` y `git diff --check`; dejar la change sin archivar ni desplegar.
