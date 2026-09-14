## Why

`DATA_MODEL.md` define la tabla `brand_assets` (logo primario, logo alternativo, referencias visuales) y `API.md` documenta sus tres endpoints, y el mockup (`starter-design/Content Suite.dc.html`) muestra una sección completa de Brand Assets dentro de Brand DNA — pero no existe ninguna change de OpenSpec que la especifique, ni migración, ni código. Es, además, una dependencia real de otra capability ya construida: `visual-compliance` (008) cita el logo primario de la marca como referencia de comparación en su auditoría multimodal. Sin Brand Assets, esa comparación no tiene de dónde leer.

## What Changes

- Especifica la capability `brand-assets`: subir/reemplazar el logo primario y el logo alternativo (slots únicos por marca), subir y eliminar referencias visuales (colección sin límite fijo), y listar los assets de una marca.
- El almacenamiento del archivo en sí SHALL apoyarse en la capability `private-storage` que `008-visual-compliance` ya especificó (validación server-side de tipo/tamaño, signed URLs de corta duración, nada público por defecto) — esta change no vuelve a especificar esos mecanismos, solo los referencia y describe cómo `brand-assets` los usa.
- **Dependencia de orden de construcción**: `private-storage` está spec'd (008) pero su código aún no existe (`008-visual-compliance` figura con 0/21 tareas). `brand-assets` no puede implementarse funcionalmente hasta que `private-storage` tenga un adapter real — esta change puede aprobarse y su spec puede archivarse de forma independiente, pero sus tasks de implementación quedan bloqueadas hasta entonces (ver `tasks.md`).
- **BREAKING**: ninguno (capability nueva).

## Capabilities

### New Capabilities
- `brand-assets`: registro del logo primario y alternativo de una marca (slot único, reemplazable), colección de referencias visuales (múltiples, eliminables individualmente), lectura por cualquier miembro de la marca (incluido Visual Compliance Reviewer, que las consume como contexto de auditoría), y escritura restringida a Creator — apoyado en `private-storage` (008) para la mecánica de almacenamiento.

### Modified Capabilities
(ninguna — `private-storage` no cambia; `brand-assets` es su consumidor, no lo modifica)

## Impact

- Código: nuevo módulo (tabla `brand_assets` ya diseñada en `DATA_MODEL.md`; migración, `app/brand_assets/` o extensión de `app/brand_dna/`, y frontend en `apps/web/src/features/brand-dna/`). Ninguno existe hoy.
- Dependencia dura: `private-storage` (008) debe tener un adapter real antes de que `brand-assets` pueda implementarse (no solo especificarse).
- Consumidor cruzado: `visual-compliance` (008) ya asume poder leer el logo primario de una marca como contexto de auditoría — esta change formaliza esa fuente de datos.
