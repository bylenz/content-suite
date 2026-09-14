## 1. Motion y base visual

- [x] 1.1 Instalar `motion` compatible en el workspace `apps/web` tras consultar Context7, actualizar lockfile y envolver la app con `MotionConfig reducedMotion="user"`; verificar imports desde `motion/react`, `npm run lint`, `npm run typecheck` y `npm run build`.
- [x] 1.2 Consolidar tokens clay, curvas y transiciones compartidas derivados exclusivamente de la paleta canónica, con hover limitado a puntero fino y fallback `prefers-reduced-motion`; verificar ausencia de `transition: all`, `scale(0)`, colores de marca nuevos y foco visible >=3:1.

## 2. Shell y Dashboard API-backed

- [x] 2.1 Refinar sidebar, encabezado y CTAs del shell hacia la composición clay de la referencia, manteniendo navegación futura deshabilitada/no interactiva; verificar roles Creator/reviewer y que Creative Studio, Approvals, Brand Audit, Observability y Create content no ejecutan navegación ni muestran datos ficticios.
- [x] 2.2 Reestructurar Dashboard con hero Deep Space Blue y tarjetas clay blancas que representen únicamente versión activa, conteos de las cinco secciones, Knowledge, health y CTA contextual desde las APIs existentes; verificar carga, vacío, error, offline, Creator sin Brand DNA y reviewer sin permisos de escritura contra API real.
- [x] 2.3 Añadir entrada de superficie y feedback de tarjetas Dashboard con Motion, usando solo opacidad/transform, stagger 40–60 ms y duración <300 ms; verificar reduced motion sin desplazamiento y no introducir pulso, parallax ni métricas ficticias de pipeline/actividad.

## 3. Brand DNA y movimiento de estado

- [x] 3.1 Refinar Brand DNA, Create y Edit con jerarquía editorial y clay tenue en lectura/formularios, conservando todos los flujos actuales de creación, edición, publicación, versiones y conflicto 409; verificar que Creator completa el flujo y que reviewers no ven controles, borradores ni metadatos de borrador.
- [x] 3.2 Implementar transiciones Motion breves e interruptibles para cambios de sección, filas de versión y feedback de publicación, sin animar inputs por tecla ni texto estable; verificar por inspección y flujo manual que usa opacidad/transform seguro, no keyframes para estado rápido y reduced motion elimina movimiento posicional.
- [x] 3.3 Añadir transición espacial al contenido del drawer móvil sin sustituir el `<dialog>` nativo; verificar teclado, Escape, foco inicial/trap/restauración y variante sin transform con `prefers-reduced-motion` en viewport móvil.

## 4. Verificación y documentación

- [x] 4.1 Ejecutar `npm run lint`, `npm run typecheck`, `npm run build` y `npm run api:test`; verificar en verde y añadir/ajustar checks de UI mínimos para cualquier lógica de motion/estado no trivial.
- [x] 4.2 Realizar revisión visual a 1440×900 y 390×844, flujos Creator/reviewer y reduced motion, comparando composición/materialidad con la captura de referencia; verificar sin overflow horizontal, sin promesas de estado no respaldadas y documentar desviaciones reales como deuda. (Baseline Dashboard/Create aprobado explícitamente por el usuario; revisión de código y de contrato independiente aprobada.)
- [x] 4.3 Ejecutar el detector Impeccable sobre los archivos web modificados, resolver findings o registrar deuda explícita, y validar `npx @fission-ai/openspec@latest validate 003-dashboard-brand-dna-motion-polish --strict`.
