# Project Context

## Problema

Los lanzamientos masivos de productos generan muchas piezas de contenido. Sin una fuente de verdad operativa, tono, restricciones y reglas visuales pueden variar entre personas, agencias y canales.

Content Suite convierte el manual de marca en un sistema utilizable por IA y por revisores humanos.

## Propuesta

```text
Brand Brief
  -> Brand DNA
  -> Brand Knowledge
  -> AI Generation
  -> Content Review
  -> Multimodal Visual Audit
  -> Final Approval
```

## Principios de producto

1. **Brand DNA es la fuente de verdad.**
2. **La IA recupera Brand Knowledge antes de generar o auditar.**
3. **Reglas críticas no dependen únicamente de similarity search.**
4. **Las decisiones de aprobación son humanas.**
5. **Cada artefacto importante es versionado.**
6. **Cada interacción AI relevante es observable.**
7. **RBAC se aplica en backend, no solamente en UI.**

## Scope del MVP

### Incluido
- Login y tres usuarios demo.
- Brand workspace.
- Brand DNA estructurado.
- Publicación y sincronización de Brand Knowledge.
- Product Description.
- Video Script.
- Image Prompt.
- Content Review.
- Visual Asset upload.
- Multimodal Brand Audit.
- Workflow history.
- Langfuse tracing.
- Deployment público.

### Fuera de scope
- Publicación automática a redes sociales.
- Editor gráfico.
- Generación de imágenes dentro de Creative Studio.
- Flujos de aprobación configurables por organización.
- Microservicios.
- Colas distribuidas.
- Billing.
- Multi-tenant enterprise avanzado.

## Workspace demo

La demo utiliza una marca de ejemplo:

- Brand: `Kinu`
- Product: `Quinoa Bites`
- Audience: `Gen Z · Peru`
- Tone: `Playful · Professional · Energetic`

Los datos demo deben ser seeds, no valores hardcodeados dentro de la lógica de dominio.

## Roles demo

### Creator
Puede crear, editar, generar, revisar consistencia y enviar.

No puede aprobar su propio contenido.

### Content Reviewer
Puede leer Brand DNA, inspeccionar contenido, Brand Knowledge y consistencia; puede aprobar o solicitar cambios.

No puede editar o regenerar contenido.

### Visual Compliance Reviewer
Puede leer contexto previo, subir/revisar un visual, ejecutar audit multimodal y aprobar o solicitar cambios.

No puede modificar Brand DNA ni contenido.

## Calidad esperada

El código debe demostrar:

- límites de dominio claros;
- structured outputs;
- validaciones;
- error handling;
- pruebas del happy path y de invariantes;
- trazabilidad;
- ausencia de secretos en código;
- documentación suficiente para continuar con agentes.
