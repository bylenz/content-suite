# AGENTS.md

Estas reglas aplican a todo agente o subagente que modifique este repositorio.

## 1. Lectura obligatoria

Antes de implementar:
1. `PROJECT_CONTEXT.md`
2. `ARCHITECTURE.md`
3. `MODULES.md`
4. documento específico del cambio;
5. change activa de OpenSpec en `openspec/changes/` y los artefactos indicados por `openspec instructions apply --change <nombre> --json`.
6. `docs/UI_UX.md` y `starter-design/Content Suite.dc.html` si se modifica frontend.

No leer todos los documentos indiscriminadamente si la tarea no los necesita.

## 2. Source of truth

Orden de precedencia:

1. requirements y tareas de la change activa de OpenSpec;
2. ADR aceptado;
3. documentos root de arquitectura;
4. código y tests existentes.

Si hay contradicción, no inventar una resolución. Reportarla.

## 3. Scope discipline

Implementar solo lo solicitado por la change activa de OpenSpec. Antes de editar, ejecutar `npx @fission-ai/openspec@latest instructions apply --change <nombre> --json` y leer todos sus `contextFiles`.

No:
- agregar microservicios;
- introducir librerías grandes sin necesidad;
- refactorizar módulos no relacionados;
- crear nuevas abstracciones “por si acaso”;
- cambiar arquitectura sin ADR.

## 4. Arquitectura

Backend:
- router -> application service -> domain policy/repository/capability;
- no SQL en routers;
- no provider SDKs en routers;
- no state transitions controladas por frontend;
- AI Platform no cambia workflow states.

Frontend:
- Vite + React + TypeScript;
- feature-first;
- no Redux sin ADR;
- TanStack Query para server state;
- React Hook Form + Zod para formularios cuando aplique.

## 5. AI

- usar provider adapters;
- structured outputs para contratos críticos;
- validar con Pydantic;
- registrar trace Langfuse;
- nunca fallback silencioso sin Brand Knowledge;
- no usar raw chain-of-thought;
- persistir solo evidencia/resumen/structured outputs necesarios.

## 6. Seguridad

- nunca commit de secretos;
- auth no equivale a authorization;
- validar brand membership en backend;
- Storage privado por defecto;
- usar signed URLs;
- no confiar en role enviado por frontend.

## 7. Versionado

Nunca sobrescribir:
- Brand DNA publicado;
- creative version enviada;
- visual asset auditado.

Crear nueva versión.

## 8. Workflow

Toda transición:
- valida rol;
- valida current state;
- persiste cambio;
- persiste workflow event;
- es transaccional cuando corresponde.

## 9. Tests

Cada cambio de dominio debe cubrir:
- happy path;
- permiso inválido;
- transición inválida;
- error externo relevante.

AI tests no deben depender siempre de llamadas reales. Usar fakes/adapters.

## 10. Done criteria

Antes de declarar terminado:
- format/lint;
- typecheck;
- tests;
- migrations coherentes;
- no secrets;
- docs actualizadas solo si cambió contrato;
- reportar archivos modificados;
- reportar comandos ejecutados;
- reportar deuda o supuestos.

## 11. Commits

Preferir commits pequeños por capacidad:
- `feat(identity): ...`
- `feat(brand-dna): ...`
- `test(workflow): ...`
- `docs(architecture): ...`

## 12. Tooling y dependencias

- El repositorio es un monorepo estructurado: Turborepo orquesta las tareas entre apps, pero `apps/api` sigue siendo el modular monolith de dominio.
- Antes de agregar o actualizar una librería, consultar Context7 para su documentación y versión estable actual; si Context7 no dispone de la librería exacta, verificar la documentación oficial y el registry. Instalar solo una versión compatible con el stack existente y registrar el cambio en el lockfile correspondiente.
- Las dependencias Python del backend se gestionan exclusivamente con `uv` (`uv add`, `uv sync`, `uv run`); no usar `pip`, `requirements.txt`, Poetry ni gestores paralelos.
- Las dependencias del frontend se instalan en su workspace npm, nunca dentro de `apps/api`.
- `starter-design/Content Suite.dc.html` contiene la referencia base de todas las pantallas y secciones. Reutilizar su jerarquía y flujos relevantes con claymorphism azul más marcado; no implementar pantallas fuera de la change activa.
- Para las superficies elevadas del frontend, usar Clay CSS tras validarlo con Context7. Mantener relieve reducido en contenido denso, contraste WCAG AA y estados semánticos legibles.

## 13. Al terminar una change de OpenSpec

Responder con:
1. resumen;
2. archivos principales;
3. decisiones;
4. tests ejecutados;
5. riesgos/deuda;
6. siguiente change sugerida.

Validar con `npx @fission-ai/openspec@latest validate <nombre> --strict` y no archivar ni comenzar la siguiente change sin instrucción.
