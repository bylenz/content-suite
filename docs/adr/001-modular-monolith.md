# ADR-001 — Monorepo estructurado + Modular Monolith

**Status:** Accepted

## Context

El reto necesita varios dominios, pero un despliegue simple y demostrable.

## Decision

Usar un monorepo estructurado con Turborepo para orquestar tareas entre apps y una sola API FastAPI con módulos internos por dominio.

Turborepo no divide el backend en servicios: `apps/api` conserva una única frontera de despliegue y autoridad de dominio. Las dependencias Python de esa app se gestionan con `uv`; las del frontend con su workspace npm.

## Consequences

### Positive
- despliegue simple;
- transacciones directas;
- tareas consistentes entre frontend y backend;
- menor overhead;
- límites claros para agentes.

### Negative
- escala independiente no disponible inicialmente;
- disciplina interna necesaria para evitar acoplamiento.

## Rejected

Microservicios: complejidad operativa injustificada para el MVP.
