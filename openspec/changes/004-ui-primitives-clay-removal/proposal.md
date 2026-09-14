## Why

`claymorphism-css` sostiene clases base de las superficies aprobadas, pero añade una dependencia innecesaria para un sistema visual que ya está definido por tokens propios. Se necesita retirarla sin sustituir el Dashboard ni Create Brand DNA por un dashboard genérico, usando primitives source-owned de shadcn/ui y Tailwind.

## What Changes

- Eliminar `claymorphism-css` del workspace web, lockfile e import global.
- Inicializar shadcn/ui compatible con Vite, React 19 y Tailwind v4, y añadir únicamente primitives requeridas por controles existentes.
- Reimplementar las superficies clay, CTA, chips e inset con CSS/Tailwind propio derivado de la paleta canónica y preservar la estructura, interacción, Motion, drawer nativo, RBAC y contratos existentes.
- Migrar controles existentes selectivamente a primitives source-owned sin introducir rutas, datos o capacidades nuevas.

## Capabilities

### New Capabilities

- Ninguna. Es una sustitución de implementación visual sin comportamiento de producto nuevo.

### Modified Capabilities

- Ninguna. Los requisitos existentes de Dashboard y Brand DNA se conservan; no se alteran contratos de capacidad.

## Impact

Afecta `apps/web`, `package-lock.json`, estilos globales y documentación de dependencias. No cambia API, backend, migraciones, datos ni autorización.
