## Context

Ver `proposal.md`. El CSS actual importa Clay CSS y las superficies aprobadas combinan su clase base `.clay` con tokens locales. El export de `starter-design/` ya define la jerarquía, paleta y sombras que se deben conservar. shadcn/ui aún no está inicializado; Tailwind v4 y Vite sí.

## Goals / Non-Goals

**Goals:**

- Reemplazar la dependencia por source-owned primitives accesibles y superficies CSS propias.
- Preservar composición, contraste, relieve selectivo, navegación, drawer nativo y flujos aprobados.
- Reducir la migración a un cambio frontend reversible con validación visual y funcional.

**Non-Goals:**

- No cambiar contratos backend, rutas, API, roles, datos ni motion.
- No convertir el diseño a defaults de shadcn, ni sustituir el `<dialog>` del drawer por Sheet.
- No crear capacidades de producto, datos demo ni componentes que no reemplacen un patrón actual.

## Decisions

### Usar shadcn como código fuente, no como tema ni runtime único

Se inicializará shadcn con la configuración actual Vite/Tailwind v4 y se agregarán sólo Button, Card, Badge, Input, Textarea y Label si eliminan duplicación existente. Sus fuentes vivirán en `src/components/ui` y se adaptarán a los tokens Content Suite. Esto preserva control y evita que el look default contradiga `starter-design/`.

Alternativa descartada: eliminar Clay CSS y reemplazar todo por utilidades ad hoc. Aunque posible, no cumple la petición de primitives shadcn ni centraliza patrones de control accesible.

### Recrear la capa material propia en CSS

`index.css` dejará de importar Clay CSS y definirá clases locales para tarjeta, profunda, chip, inset y CTA con bordes, sombras e inset actuales. La migración puede conservar aliases `.clay-*` temporalmente para acotar churn, pero `.clay` no dependerá de un paquete externo. Los colores y sombras se derivan de los tokens canónicos existentes.

Alternativa descartada: cambiar de golpe todas las clases de JSX. Genera diffs masivos y riesgo visual sin aportar comportamiento.

### Conservar primitivas nativas críticas

El drawer móvil sigue siendo `<dialog>` con su manejo de Escape, focus trap/restauración y Motion interior. Button shadcn sólo se aplica cuando no sustituye semántica nativa o eventos existentes.

### Instalar dependencias mínimas verificadas

Antes de instalar se consultará Context7 y el registry/CLI de shadcn. El lockfile se actualiza mediante npm workspace. No se añade una librería de iconos, Sheet u otra dependencia salvo que la generación de una primitive realmente seleccionada la requiera.

## Risks / Trade-offs

- [La clase `.clay` desaparece y altera superficies] → recrear la clase base local y comparar las rutas aprobadas antes de borrar aliases.
- [shadcn modifica aliases/configuración TypeScript] → revisar y limitar `components.json`, tsconfig y Vite a los cambios requeridos; no modificar importaciones no relacionadas.
- [Primitives defaults erosionan el diseño] → tokens/variants propios y revisión contra `starter-design/` en desktop/móvil.
- [Cambio de elementos interactivos afecta foco/form submit] → mantener elementos nativos donde proceda y probar teclado, roles Creator/reviewer y errores.

## Migration Plan

1. Baseline: inventariar imports/clases y comprobar lint/typecheck/build.
2. Inicializar shadcn y añadir primitives mínimas en source.
3. Definir equivalentes locales de superficie, migrar controles selectivamente y retirar import/dependencia Clay CSS.
4. Ejecutar lint/typecheck/build, detector Impeccable y revisión funcional/visual Creator-reviewer, móvil y reduced motion.
5. Si falla la paridad, revertir las primitives/CSS de esta change y restaurar el lockfile; no hay migraciones ni datos que revertir.
