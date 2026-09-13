# Modules

## 1. Identity & RBAC

### Responsabilidad
Resolver usuario autenticado, membresía de brand y permisos.

### No hace
No genera contenido ni conoce prompts.

### Capacidades
- current user;
- memberships;
- roles;
- permission guards.

---

## 2. Brand DNA

### Responsabilidad
Administrar el documento canónico y versionado de reglas de marca.

### Capacidades
- draft;
- AI-assisted generation;
- edit;
- publish;
- versions;
- assets de marca.

### Salida
`BrandDNAVersion`

Al publicar, solicita sincronización al módulo Knowledge.

---

## 3. Knowledge / RAG

### Responsabilidad
Transformar Brand DNA publicado en Brand Knowledge recuperable.

### Capacidades
- chunk building;
- metadata;
- embeddings;
- mandatory rule retrieval;
- semantic retrieval;
- task-specific context building;
- sync status.

### Regla
pgvector no es fuente de verdad.

---

## 4. Creative

### Responsabilidad
Crear artefactos de contenido versionados.

### Tipos
- product description;
- video script;
- image prompt.

### Capacidades
- create draft;
- generate;
- regenerate;
- manual edit as new version;
- consistency check;
- submit exact version.

---

## 5. Governance

### Responsabilidad
Revisión semántica humana.

### Actor
Content Reviewer.

### Capacidades
- review queue;
- inspect submitted version;
- inspect applied context;
- approve;
- request changes;
- history.

### Invariante
Nunca modifica el contenido.

---

## 6. Visual Audit

### Responsabilidad
Auditoría multimodal y decisión visual final.

### Actor
Visual Compliance Reviewer.

### Capacidades
- upload/version visual asset;
- retrieve visual Brand Knowledge;
- run multimodal audit;
- deterministic score;
- findings;
- request changes;
- approve;
- exception acceptance;
- audit history.

---

## 7. AI Platform

### Responsabilidad
Exponer capacidades AI estables al dominio.

### Contiene
- agents/capabilities;
- provider adapters;
- prompt registry;
- structured contracts;
- scoring helpers;
- tracing integration.

### No hace
No cambia estados de workflow.

---

## 8. Observability

### Responsabilidad
Instrumentar AI flows y enlazar entidades con Langfuse traces.

La UI in-app puede implementarse al final. El tracing no.
