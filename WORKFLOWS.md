# Workflows

## Main Workflow

```mermaid
stateDiagram-v2
  [*] --> DRAFT
  DRAFT --> PENDING_CONTENT_REVIEW: Creator submits

  PENDING_CONTENT_REVIEW --> CONTENT_CHANGES_REQUESTED: Reviewer requests changes
  CONTENT_CHANGES_REQUESTED --> PENDING_CONTENT_REVIEW: Creator resubmits new version

  PENDING_CONTENT_REVIEW --> CONTENT_APPROVED: Reviewer approves
  CONTENT_APPROVED --> PENDING_VISUAL_REVIEW: Visual submitted

  PENDING_VISUAL_REVIEW --> VISUAL_CHANGES_REQUESTED: Visual reviewer requests changes
  VISUAL_CHANGES_REQUESTED --> PENDING_VISUAL_REVIEW: New visual version

  PENDING_VISUAL_REVIEW --> FINAL_APPROVED: Visual reviewer approves
  FINAL_APPROVED --> [*]
```

## Brand DNA lifecycle

```mermaid
stateDiagram-v2
  [*] --> DRAFT
  DRAFT --> ACTIVE: publish
  ACTIVE --> ACTIVE: publish new version

  state Knowledge {
    [*] --> NOT_SYNCED
    NOT_SYNCED --> SYNCING
    SYNCING --> SYNCED
    SYNCED --> OUTDATED: draft changes
    OUTDATED --> SYNCING: publish changes
    SYNCING --> FAILED: sync error
    FAILED --> SYNCING: retry
  }
```

## Content submission

1. Creator selecciona una `creative_version`.
2. Backend verifica:
   - role = CREATOR;
   - version pertenece al item;
   - Brand Knowledge requerido disponible;
   - estado permite submit.
3. `creative_item.workflow_status = PENDING_CONTENT_REVIEW`.
4. Se registra `workflow_event`.
5. La versión enviada queda congelada.

## Request Changes

No se modifica la versión rechazada.

```text
v3 submitted
 -> Changes Requested
 -> creator edits
 -> v4 created
 -> v4 submitted
```

## Content Approval

Aprobación semántica no significa aprobación visual.

```text
CONTENT_APPROVED
  -> visual asset version
  -> multimodal audit
  -> human visual decision
```

## Visual exception

Si existe un finding HIGH, el reviewer puede aprobar de todas formas.

Debe quedar:
- finding;
- decision;
- `exception_accepted = true`;
- actor;
- timestamp.

## Guards

Transitions inválidas se rechazan en backend.

Ejemplos:
- Creator intenta aprobar -> 403.
- Reviewer intenta editar -> 403.
- Approve desde `DRAFT` -> 409.
- Submit v3 y modificar v3 -> no permitido; crear v4.
