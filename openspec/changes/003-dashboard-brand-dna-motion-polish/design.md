## Context

Las superficies existentes ya consumen Brand DNA y health reales, y el shell posee tokens clay de la paleta canónica, foco visible, drawer móvil nativo y una regla CSS para movimiento reducido. La captura proporcionada confirma la composición objetivo: sidebar claro elevado, hero azul profundo y tarjetas blancas blandas. La API no expone contratos para pipeline, actividad, approvals, audit ni generación. Véanse `proposal.md` y la spec para el comportamiento observable.

## Goals / Non-Goals

**Goals:**
- Acercar Dashboard y Brand DNA existentes a la composición y materialidad de la referencia sin modificar su fuente de verdad.
- Añadir movimiento intencional, interruptible y reducido globalmente para pantallas y estados ocasionales.
- Mantener la privacidad de borradores, RBAC y accesibilidad del shell durante la mejora visual.

**Non-Goals:**
- Crear endpoints, modelos, datos demo o workflows para pipeline, actividad, Knowledge Sync, Creative, approvals, audit u observabilidad.
- Reemplazar el diálogo móvil nativo, añadir animaciones continuas, ni animar campos por pulsación.
- Cambiar el contrato de Brand DNA, sus errores o la semántica de publicación.

## Decisions

### Motion React como única capa de animación programática
Se instalará `motion` y se importará desde `motion/react`, compatible con React 19 del workspace. `MotionConfig reducedMotion="user"` envolverá la aplicación para que el sistema desactive transform/layout motion globalmente; componentes que necesiten distinguir la variante usarán `useReducedMotion`.

Se elige Motion porque las transiciones de secciones, el lifecycle de entrada/salida y el drawer requieren estado y salida interruptible. CSS seguirá siendo la opción para hover/press simples y tokens; no se añadirá una segunda librería. Context7 valida `motion/react`, `MotionConfig` y `useReducedMotion`.

### Motion limitado por propósito y frecuencia
Las entradas de Dashboard/Brand DNA tienen el propósito de evitar un cambio abrupto y se ejecutan al cargar o cambiar de superficie. Usarán `opacity` y `transform: translateY(...)`, con stagger de 40–60 ms, curva `cubic-bezier(0.23, 1, 0.32, 1)` y 180–240 ms. Cambios de sección serán crossfade de opacidad breve; éxito/error de publicación y drawer usarán opacidad más transform, sin keyframes ni escalado desde cero.

No se animan teclado, formularios por escritura, navegación de alta frecuencia, ni cuerpo editorial persistente. Hover/press permanece CSS y se acota a `(hover: hover) and (pointer: fine)`.

### Refactor visual sobre datos reales
Dashboard reordenará únicamente datos disponibles: versión, cinco conteos, Knowledge, estado de health y CTA contextual. La readiness será una presentación derivada que nunca prometa sincronización/generación fuera del DTO. Los elementos de la referencia sin backend conservarán la navegación ya deshabilitada o se presentarán como futuros, sin números/eventos estáticos que se confundan con producto real.

Brand DNA conservará la densidad editorial y empleará clay fuerte solo para navegación, hero, estados y tarjetas cortas. Formularios y documento usan relieve tenue, foco existente y contraste AA.

### Drawer móvil conserva la semántica nativa
El `<dialog>` actual sigue siendo el control modal, con Escape, foco y restauración intactos. Se anima solamente el contenedor interior al abrir/cerrar cuando la plataforma no reduce movimiento; no se sustituye por un portal manual ni se usa layout motion para el diálogo.

## Risks / Trade-offs

- [Motion incrementa el bundle web] → se limita a las superficies existentes, se evita animar listas grandes y se verifican build y carga visual.
- [El refinamiento puede insinuar estados que la API no conoce] → cada copy/CTA de estado deriva de `active`, `knowledge_status`, conteos o health; sin datos se usa vacío explícito.
- [El motion puede degradar foco del drawer] → se conserva diálogo nativo y se prueba teclado, Escape y restauración de foco en móvil.
- [Clay excesivo reduce escaneabilidad] → solo superficies elevadas usan relieve fuerte; formulario y lectura siguen planos/tenues.

## Migration Plan

1. Instalar `motion` en el workspace web y actualizar el lockfile.
2. Incorporar configuración global de reduced motion y tokens compartidos sin cambiar APIs.
3. Refinar shell, Dashboard y Brand DNA sobre los DTOs actuales.
4. Validar Creator/reviewer, reduced motion, desktop/móvil, foco del drawer y detector Impeccable.
5. Rollback: revertir exclusivamente la dependencia y archivos web de esta change; API y datos no cambian.
