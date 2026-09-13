# UI / UX Context

## Fuente de diseño

`starter-design/Content Suite.dc.html` es la guía visual base y contiene las pantallas de referencia del producto. Consultarla antes de modificar frontend; extraer de ella solo los flujos que la change activa de OpenSpec requiere. No copiar su JavaScript ni convertir el HTML de diseño en la aplicación.

## Visual language

Design system aprobado:
- clean;
- premium;
- AI-native;
- claymorphism azul, visible y consistente;
- blue primary palette;
- editorial surfaces para contenido largo;
- strong clay para navegación, hero cards, decisiones, estados y AI context.

## Materialidad clay

Todas las pantallas y secciones de `starter-design/` comparten el mismo sistema: sidebar clara y elevada, navegación con selección azul acolchada, tarjetas blancas de radio amplio, paneles principales azul profundo, métricas pastel y CTAs azules con profundidad. La captura de referencia confirma esta dirección.

Usar [Clay CSS](https://codeadrian.github.io/clay.css/) como capa base en superficies elevadas y definir tokens propios para fondo, radios, sombras interiores y sombras exteriores. El efecto debe leerse como material suave y táctil, no como blur genérico: borde de luz sutil, sombra azul/gris tintada y relieve consistente. No aplicar clay a cada línea, input o bloque de texto; las superficies de datos y formularios mantienen una versión tenue para legibilidad y contraste WCAG AA.

## Paleta canónica

Esta es la única paleta base del producto. Definir tokens semánticos a partir de estos valores, sin introducir colores de marca adicionales: Strawberry Red `#E63946` (error, acción destructiva), Honeydew `#F1FAEE` (canvas claro), Frosted Blue `#A8DADC` (superficies suaves y estados informativos), Steel Blue `#457B9D` (acción secundaria y gráficos) y Deep Space Blue `#1D3557` (navegación, títulos y paneles profundos). El azul accesible para CTA debe derivar de Steel Blue o Deep Space Blue; Strawberry Red nunca es primario decorativo.

## Shell

Sidebar persistente:

```text
Dashboard
Brand DNA
Creative Studio
Approvals
Brand Audit
Observability
```

La navegación se adapta por rol sin convertir cada rol en una aplicación diferente.

## Roles

### Creator
Activos:
- Dashboard
- Brand DNA
- Creative Studio

Puede ver status de revisiones.

### Content Reviewer
Activos:
- Dashboard
- Approvals

Brand DNA read-only.

### Visual Reviewer
Activos:
- Dashboard
- Brand Audit

Brand DNA / previous review context read-only.

## UX principles

- Creative Studio no es chatbot.
- Brand DNA parece documento operativo, no blob Markdown.
- Applied Brand Context hace visible el RAG sin exponer embeddings.
- AI score ayuda; humano decide.
- Request Changes en UI, aunque internamente el backend modele un estado equivalente.
- No generar contenido si required Brand Knowledge falla.

## Implementation note

La referencia en `starter-design/` guía estructura, jerarquía, componentes, estados y flujos de todas las pantallas. Este documento define comportamiento y consistencia, no valores pixel-perfect ni alcance funcional adicional. OpenSpec limita qué se construye en cada change.
