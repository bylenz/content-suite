# Contributing

## Branches

Sugerencia:
```text
feat/<scope>-<short-name>
fix/<scope>-<short-name>
docs/<short-name>
```

## Before coding

- localizar la change activa con `npx @fission-ai/openspec@latest list --json`;
- ejecutar `npx @fission-ai/openspec@latest instructions apply --change <nombre> --json` y leer sus `contextFiles`;
- identificar módulos tocados;
- revisar `starter-design/Content Suite.dc.html` si cambia frontend;
- confirmar que no requiere ADR;
- antes de agregar o actualizar una librería, consultar Context7 y confirmar la versión estable compatible.

## Pull Request checklist

- [ ] scope coincide con los requirements y tasks de OpenSpec;
- [ ] tasks de la change actualizados únicamente tras completar su trabajo;
- [ ] `npx @fission-ai/openspec@latest validate <nombre> --strict` pasa;
- [ ] lockfile actualizado; `uv.lock` para backend y lockfile npm para frontend;
- [ ] tareas relevantes ejecutadas mediante Turbo y comandos Python con `uv run`;
- [ ] tests;
- [ ] lint/typecheck;
- [ ] migrations revisadas;
- [ ] no secrets;
- [ ] API/docs actualizadas si cambió contrato;
- [ ] no cambios no relacionados.

## Architecture changes

Cambios a:
- database choice;
- auth strategy;
- monolith boundaries;
- RAG strategy;
- provider abstraction;

requieren ADR nuevo o actualización explícita de uno existente.
