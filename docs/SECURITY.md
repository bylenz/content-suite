# Security

## Threat model mínimo

### Authorization bypass
Mitigación:
- server-side RBAC;
- brand membership check;
- resource ownership/brand check.

### Secret leakage
Mitigación:
- provider keys backend-only;
- redactar prompts/logs cuando corresponda;
- no secrets en frontend.

### Storage exposure
Mitigación:
- private buckets;
- signed URLs;
- validate file type/size.

### Prompt injection / user input
Mitigación:
- separar system instructions, Brand Context y user brief;
- structured outputs;
- no conceder herramientas arbitrarias al modelo.

### Cross-brand retrieval
Mitigación:
- mandatory `brand_id` + `brand_dna_version_id` filters antes de vector retrieval.

### Workflow tampering
Mitigación:
- state guards;
- backend transitions;
- append workflow events.

## Uploads

Validar:
- MIME;
- extension;
- max size;
- image decodability.

No confiar únicamente en filename.

## Logging

No loggear:
- tokens;
- passwords;
- secrets;
- JWT completos.

PII mínima en Langfuse.
