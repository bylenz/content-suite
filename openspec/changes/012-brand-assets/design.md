## Context

`DATA_MODEL.md` ya fija el esquema de `brand_assets` (`id`, `brand_id`, `brand_dna_version_id` nullable, `type` enum `PRIMARY_LOGO|ALT_LOGO|VISUAL_REFERENCE`, `storage_path`, `metadata` jsonb, `created_at` — sin `updated_at` ni soft-delete) y `API.md` ya fija las tres rutas (`POST/GET /brands/{brand_id}/assets`, `DELETE /brands/{brand_id}/assets/{asset_id}`). Esta change no cambia ese contrato ya documentado; lo formaliza como capability y decide el comportamiento que esos documentos no explicitan. Ver `proposal.md - Why`.

## Goals / Non-Goals

**Goals:**
- Formalizar el comportamiento de slot único (logos) vs. colección (referencias) que el mockup ya muestra pero ningún documento de contrato fija.
- Dejar explícita la dependencia con `private-storage` (008) sin duplicar su especificación.

**Non-Goals:**
- No especifica ni modifica `private-storage` (008) — solo lo consume.
- No incluye una vista de comparación lado-a-lado ni herramientas de edición de imagen; eso es consumo desde `visual-compliance`, no responsabilidad de esta capability.
- No versiona los brand assets (a diferencia de `brand_dna_versions`/`creative_versions`): reemplazar un logo no dispara la creación de una versión de Brand DNA nueva ni requiere aprobación.

## Decisions

**Sin `updated_at` en el esquema → "reemplazar" es delete+insert, no un UPDATE.**
`DATA_MODEL.md` no incluye `updated_at` en `brand_assets`, consistente con el resto del sistema (filas normalmente insert-only). Reemplazar un logo se modela como eliminar la fila anterior de ese `type` y crear una nueva, en una transacción — nunca una actualización en sitio del `storage_path`. Alternativa descartada: permitir `UPDATE storage_path` in place, que rompería el patrón insert/delete-only que ya siguen `creative_versions` y `workflow_events`, y complicaría la limpieza del objeto de storage huérfano.

**`brand_dna_version_id` es un snapshot de auditoría, no una relación de pertenencia.**
Un brand asset pertenece a la marca (`brand_id`), no a una versión de Brand DNA específica — los logos deben seguir siendo legibles y válidos aunque la marca publique una versión nueva. `brand_dna_version_id` solo registra cuál era la versión `ACTIVE` al momento de la subida, igual que `creative_versions.brand_dna_version_id` ya hace para el contenido creativo. Alternativa descartada: atar el asset a una versión y exigir volver a subirlo en cada publicación — contradice el mockup, donde los logos son una sección estable de Brand DNA, no parte del documento versionado.

**No se especifica un límite de cantidad de `VISUAL_REFERENCE`.**
El mockup muestra "3 images" como dato de ejemplo, no como límite declarado en ningún documento de contrato. Fijar un número aquí sería inventar una regla de producto sin fuente — se deja como un límite de implementación razonable (p. ej. una constante de configuración) fuera del alcance de este spec, igual que `private-storage` ya deja el tamaño máximo de archivo como "configurado" sin fijar el valor en la spec.

**Reglas de autorización 403 vs. 404 siguen el precedente ya sentado en `011-creative-studio`.**
Una acción sin recurso existente que proteger (listar, subir) responde 403 a un no-miembro; una acción sobre un recurso existente (eliminar un `asset_id`) responde 404 indistinguible de "no existe". Mismo razonamiento que `011-creative-studio`'s "Escritura restringida a Creator con membresía" (creación vs. edición de un item existente).

## Risks / Trade-offs

- [Bloqueo de implementación: `private-storage` no tiene código aún] → Esta spec puede archivarse y quedar disponible igual; sus tasks de implementación (no incluidas aquí, se derivan cuando se implemente) quedan explícitamente condicionadas a que 008 tenga un adapter real primero. No es un riesgo de la spec en sí, es una dependencia de secuencia documentada en `proposal.md`.
- [Objetos huérfanos en storage si el delete+insert del reemplazo de logo falla a la mitad] → La misma garantía transaccional que `private-storage` ya exige ("sin registros huérfanos" en su Requirement de validación) cubre este caso: la operación de reemplazo se implementa sobre el mismo puerto, con la misma disciplina de no dejar objetos sin fila o filas sin objeto.

## Migration Plan

No aplica implementación en esta change (solo especificación). Cuando se implemente: migración Alembic para `brand_assets` (con la misma extensión de RLS que `007`/`011` ya establecieron como pendiente-y-luego-cerrada para tablas nuevas — no debe repetirse el gap de `creative_items` quedando sin RLS al nacer).

## Open Questions

(ninguna)
