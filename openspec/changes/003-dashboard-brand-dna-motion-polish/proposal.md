## Why

Las superficies funcionales de Dashboard y Brand DNA ya existen, pero todavía no traducen con suficiente fidelidad el lenguaje claymorphism premium de la referencia ni comunican sus cambios de estado con movimiento accesible. Esta change consolida esa experiencia sin inventar datos o adelantar las capacidades de Creative, approvals, audit, activity o Knowledge Sync.

## What Changes

- Rediseñar únicamente Dashboard y las superficies existentes de Brand DNA/Create/Edit con sidebar elevado, panel de readiness azul profundo, tarjetas clay blancas, métricas reales de Brand DNA y CTAs Steel Blue derivados de la paleta canónica.
- Añadir Motion para React (`motion/react`) para entradas de superficie, transiciones de secciones, feedback de publicación y microinteracciones de tarjetas/navegación; respetar `prefers-reduced-motion` globalmente y no animar edición frecuente ni contenido largo durante lectura.
- Mantener los widgets de Content Pipeline, Recent Activity, Approvals, Brand Audit, Creative Studio y Create content deshabilitados y explícitamente futuros: la API actual no provee contratos para sus datos.
- Preservar el contrato API, RBAC, privacidad de borradores, flujos Creator/reviewer y accesibilidad existente del drawer móvil.

## Capabilities

### New Capabilities
- `dashboard-brand-dna-experience`: experiencia visual y de motion accesible para las superficies API-backed de Dashboard y Brand DNA.

### Modified Capabilities
- Ninguna.

## Impact

- Afecta `apps/web` (shell, Dashboard, Brand DNA/Create/Edit, CSS y rutas de sesión) y `package-lock.json`.
- Añade la dependencia frontend `motion`; no cambia modelos, endpoints, migraciones ni contratos de API.
- Requiere revisión visual desktop/móvil, reduced motion, flujos Creator/reviewer y detector Impeccable.
