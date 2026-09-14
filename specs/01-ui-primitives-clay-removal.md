# Objective

Eliminar `claymorphism-css` y sustituir su mecanismo por primitives locales basadas en shadcn/ui y Tailwind/CSS propio, conservando la apariencia y comportamiento aprobados de Dashboard y Brand DNA.

# Current State

`apps/web/src/index.css` importa Clay CSS y define tokens sobre sus variables; alrededor de 40 usos JSX dependen de `.clay`. Tailwind v4, React 19 y Motion ya existen. No hay `components.json`, aliases, `components/ui` ni dependencias shadcn.

# In Scope

- Inicializar shadcn/ui para Vite + Tailwind v4 según su documentación vigente.
- Añadir únicamente primitives que reemplacen patrones reales: Button, Card, Badge, Input, Textarea y Label; Sheet no reemplaza el `<dialog>` accesible existente.
- Remover `claymorphism-css` de `apps/web/package.json`, lockfile e `index.css`.
- Reimplementar el relieve actual con tokens propios Tailwind/CSS: tarjeta clara, panel profundo, chip, superficie editorial, inset, CTA y selección de nav.
- Migrar o compatibilizar clases de los componentes existentes sin cambiar rutas, datos, copy, RBAC, privacidad de borradores, Drawer nativo ni Motion.
- Validar a11y, foco, reduced motion, desktop y móvil.

# Out of Scope

- Rediseñar Dashboard o Create/Edit Brand DNA.
- Añadir páginas, rutas, datos de pipeline/actividad, backend o una librería visual adicional.
- Sustituir React Hook Form/Zod/TanStack Query o `motion/react`.

# Domain / Modules Affected

Solo `apps/web`: diseño compartido, shell, Dashboard, estados y Brand DNA. Sin dominio backend.

# Database Changes

Ninguno.

# API Changes

Ninguno.

# Frontend Changes

- Configurar alias y `components.json` únicamente si lo exige el CLI de shadcn.
- Generar source-owned primitives bajo `src/components/ui` y adaptarlas al sistema cromático existente, no a los defaults genéricos de shadcn.
- Mantener la paleta canónica y sombras suaves de `starter-design/Content Suite.dc.html`; las superficies densas continúan con relieve reducido.
- Convertir controles existentes a Button/Input/Textarea/Label cuando el primitive reduzca duplicación sin alterar DOM crítico, especialmente el `<dialog>` nativo.

# AI / RAG Changes

Ninguno.

# Security / RBAC Requirements

La migración no puede cambiar guards de sesión, selección de marca, roles ni visibilidad de borradores.

# Observability Requirements

Ninguno.

# Acceptance Criteria

- No quedan referencias a `claymorphism-css` ni a su import en el árbol web/lockfile.
- Dashboard y Create Brand DNA conservan jerarquía, materialidad azul, espaciado, drawer y flujos aprobados.
- Las primitives shadcn añadidas son source-owned, accesibles y usan tokens de Content Suite.
- No hay `transition: all`, movimiento sin reduced-motion, colores de marca fuera de la paleta ni controles futuros interactivos.

# Tests Required

- `npm run lint`, `npm run typecheck`, `npm run build`.
- Prueba de smoke/manual de navegación Dashboard/Create/Edit por Creator y lectura por reviewer.
- Inspección de foco teclado y contraste de CTA/formulario; detector Impeccable una vez sobre archivos modificados.

# Manual Verification Steps

1. Abrir la app a 1440×900 y 390×844.
2. Comparar sidebar, hero, cards, CTA, formularios y estados con `starter-design/` y la captura del usuario.
3. Probar dialog de menú con teclado/Escape y `prefers-reduced-motion`.
4. Comprobar que Creator guarda/publica y reviewer no ve borradores.

# Stop Condition

Detener y restaurar el primitive afectado si la sustitución cambia el layout aprobado, accesibilidad o contrato de sesión. No continuar a Brand Knowledge hasta que estas comprobaciones pasen.
