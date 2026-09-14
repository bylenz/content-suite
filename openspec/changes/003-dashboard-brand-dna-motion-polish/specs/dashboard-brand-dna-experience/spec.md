## Purpose

Ofrece una experiencia Dashboard y Brand DNA coherente, premium y accesible que comunica estados reales de marca mediante superficies clay y movimiento reducido cuando el usuario lo solicita.

## ADDED Requirements

### Requirement: Dashboard representa únicamente el estado real de Brand DNA
El Dashboard SHALL mostrar el estado de readiness, versión activa, conteos de las cinco secciones y estado de Knowledge a partir de las respuestas existentes de Brand DNA y health. SHALL mostrar una acción hacia Brand DNA o su creación según el estado y el rol, sin afirmar sincronización ni capacidad de generación que la API no confirme.

#### Scenario: Marca con versión activa
- **WHEN** la API devuelve una versión Brand DNA activa
- **THEN** el Dashboard muestra su versión, conteos y estado de Knowledge reales en tarjetas visuales legibles

#### Scenario: Marca sin versión activa
- **WHEN** la API devuelve que no existe una versión Brand DNA activa
- **THEN** el Creator recibe una acción hacia Create Brand DNA y un reviewer recibe una explicación de solo lectura

### Requirement: Capacidades futuras permanecen honestamente inactivas
La interfaz SHALL conservar Content Pipeline, Recent Activity, Creative Studio, Approvals, Brand Audit, Observability y Create content como elementos visualmente deshabilitados o etiquetados como futuros mientras no exista un contrato de datos y workflow para ellos. SHALL NOT renderizar métricas, eventos o resultados de ejemplo que puedan parecer datos reales.

#### Scenario: Visualización del Dashboard
- **WHEN** una persona abre el Dashboard refinado
- **THEN** no puede interpretar widgets de pipeline, actividad, approvals o audit como información real ni activarlos

### Requirement: Brand DNA conserva sus garantías funcionales durante el refinamiento
Las vistas Brand DNA, Create y Edit SHALL conservar los flujos existentes de lectura, creación, edición, publicación y conflicto. Los controles de escritura SHALL mostrarse solo a Creator y los reviewers SHALL NOT recibir controles ni metadatos de borradores.

#### Scenario: Reviewer consulta Brand DNA
- **WHEN** un Content Reviewer o Visual Reviewer abre Brand DNA
- **THEN** ve únicamente versiones publicadas y no ve controles, contenido ni metadatos de borrador

#### Scenario: Creator publica un borrador
- **WHEN** un Creator publica con un `expected_draft_id` vigente
- **THEN** recibe feedback de éxito y la interfaz refresca el estado sin cambiar la semántica de conflicto 409 existente

### Requirement: El lenguaje visual usa claymorphism canónico y legible
Dashboard y Brand DNA SHALL usar sidebar elevada, paneles Deep Space Blue para estados prioritarios, tarjetas blancas con relieve suave, CTAs derivados de Steel Blue y navegación activa Frosted Blue. SHALL limitar superficies clay fuertes a navegación, hero, tarjetas de estado y acciones; el contenido editorial y los formularios densos conservarán contraste y relieve tenue. SHALL NOT introducir colores de marca fuera de la paleta canónica.

#### Scenario: Revisión visual desktop
- **WHEN** se revisa la experiencia a 1440×900
- **THEN** presenta la jerarquía de sidebar, hero azul profundo y tarjetas redondeadas de la referencia sin perder legibilidad de contenido real

#### Scenario: Revisión visual móvil
- **WHEN** se revisa la experiencia a 390×844
- **THEN** no tiene desbordamiento horizontal y mantiene foco visible con contraste mínimo 3:1

### Requirement: El movimiento comunica cambios de estado respetando accesibilidad
La interfaz SHALL aplicar movimiento solo para entrada ocasional de superficies, transición de secciones, apertura/cierre del drawer móvil, feedback de publicación y microinteracciones de puntero fino. Las transiciones SHALL usar únicamente opacidad, transform o layout seguro, durar menos de 300 ms y poder interrumpirse sin glitches. La preferencia `prefers-reduced-motion` SHALL eliminar movimiento posicional y conservar feedback de opacidad/color; las acciones frecuentes de teclado, campos de formulario y texto editorial estable SHALL NOT animarse.

#### Scenario: Preferencia de movimiento reducido
- **WHEN** el sistema del usuario solicita movimiento reducido
- **THEN** las entradas, cambios de sección y drawer no desplazan ni reorganizan elementos mediante transform

#### Scenario: Cambio de sección Brand DNA
- **WHEN** una persona selecciona una sección distinta de Brand DNA
- **THEN** el contenido cambia con una transición breve de estado sin animar persistentemente el texto leído

#### Scenario: Drawer móvil accesible
- **WHEN** una persona abre y cierra el drawer móvil
- **THEN** conserva diálogo modal nativo, Escape, foco contenido y restauración de foco además de una transición espacial breve cuando no hay reduced motion
