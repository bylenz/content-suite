## Purpose

Expone capacidades AI estables al dominio mediante interfaces provider-agnostic asíncronas, contratos estructurados validados y un prompt registry versionado, sin acoplar módulos de negocio a SDKs de proveedor ni cambiar estados de workflow.

## ADDED Requirements

### Requirement: Interfaces de modelo provider-agnostic
El módulo `ai` SHALL exponer interfaces `TextModel`, `EmbeddingModel` y `VisionModel` con las operaciones `generate`, `generate_structured`, `analyze_structured` y `embed` según corresponda; todas SHALL ser asíncronas (`async def`), de modo que todo consumidor espera una corutina y ningún adapter bloquea el event loop. Los SDKs de proveedores externos MUST importarse únicamente dentro de los adapters de `ai/providers`; routers y services de dominio SHALL NOT importar SDKs de proveedor.

#### Scenario: Servicio de dominio consume una capability
- **WHEN** un service de dominio necesita generación de texto o embeddings
- **THEN** depende solo de la interfaz asíncrona `TextModel`/`EmbeddingModel` inyectada, sin importar ningún SDK de proveedor

#### Scenario: Auditoría de imports
- **WHEN** se inspeccionan estáticamente los imports de `apps/api/app`
- **THEN** no existe ninguna referencia a SDKs de proveedores de IA fuera de `ai/providers/`

### Requirement: Contratos estructurados validados
Los outputs críticos SHALL definirse como contratos Pydantic v2 con `extra="forbid"` y campos exactos: `CreativeOutput` (`content_type: Literal["product_description","video_script","image_prompt"]`, `title: str`, exactamente uno de `content: str | None` o `structured_sections: list[CreativeSection] | None`, `applied_rule_ids: list[str]`), `ConsistencyResult` y `VisualAuditResult` (ambos con `checks: list[Check]`, `findings: list[Finding]`, `summary: str`), `Finding` compartido (`rule_id`, `category`, `expected`, `detected`, `evidence`, `recommendation`, `severity: Literal["low","medium","high"]`, `status: Literal["pass","fail"]`) y `Check` (`check_id`, `label`, `status: Literal["pass","fail"]`), con los límites de longitud y cardinalidad definidos en `design.md`. El sistema SHALL validar todo output de modelo contra su contrato antes de devolverlo. Un output malformado (campo faltante, tipo incorrecto, valor fuera de enum, campo extra o exclusión mutua rota) MUST producir un error explícito de validación, nunca un texto genérico ni un passthrough sin validar. El sistema SHALL NOT persistir chain-of-thought ni razonamiento raw del modelo.

#### Scenario: Output malformado
- **WHEN** el modelo devuelve un output que no cumple su contrato
- **THEN** la ejecución falla con un error de validación explícito que identifica el contrato afectado

#### Scenario: Campo extra o enum inválido
- **WHEN** el output incluye un campo no declarado o un valor fuera de los enums permitidos
- **THEN** la validación lo rechaza por `extra="forbid"` o por el enum, sin passthrough

#### Scenario: Output válido
- **WHEN** el modelo devuelve un output conforme a su contrato
- **THEN** el consumidor recibe el objeto validado con los campos tipados del contrato

### Requirement: Prompt registry versionado
El módulo `ai` SHALL mantener un registry inmutable de prompts versionados con los IDs iniciales `brand.architect.v1`, `creative.product_description.v1`, `creative.video_script.v1`, `creative.image_prompt.v1`, `consistency.text.v1` y `audit.visual.v1`. Resolver un prompt con un ID inexistente o una versión inexistente MUST producir un error explícito. Toda ejecución SHALL registrar el `prompt_version` usado.

#### Scenario: Prompt existente
- **WHEN** se resuelve `creative.product_description.v1`
- **THEN** se obtiene la plantilla versionada correspondiente y su versión queda disponible para el trace

#### Scenario: Prompt inexistente
- **WHEN** se resuelve un ID no registrado
- **THEN** se produce un error explícito de prompt no encontrado sin invocar al modelo

### Requirement: Capabilities reciben adapters por dependencia
Las capabilities SHALL ser asíncronas, recibir sus adapters por inyección de dependencia, resolver el prompt del registry, ejecutar la llamada al modelo con `await`, validar el output y devolver el resultado estructurado junto con los metadatos de trace. La representación de proveedor no configurado SHALL ser unánime: el adapter resuelto es `None` y la capability MUST fallar con un error explícito de proveedor ausente antes de invocar el modelo; SHALL NOT existir fallback silencioso a contenido genérico. El mapeo del error a 503 ocurrirá solo en el boundary de API de las changes consumidoras.

#### Scenario: Proveedor no configurado
- **WHEN** se ejecuta una capability cuyo adapter resuelto es `None`
- **THEN** falla con un error explícito de proveedor no configurado y sin generar contenido sustituto

#### Scenario: Capability ejecutada con fake
- **WHEN** se inyecta un adapter fake determinista
- **THEN** la capability devuelve el contrato validado y los metadatos de ejecución sin llamadas de red

### Requirement: Fakes deterministas sin red
El módulo `ai` SHALL proveer fakes deterministas asíncronos de `TextModel`, `EmbeddingModel` y `VisionModel` para tests y desarrollo. Los tests de `ai` MUST ejecutarse sin llamadas de red reales.

#### Scenario: Suite de tests
- **WHEN** se ejecutan los tests del módulo `ai`
- **THEN** todas las capabilities usan fakes o no-op y no se realiza ninguna llamada de red
