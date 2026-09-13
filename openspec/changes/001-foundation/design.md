## Context

Ver `proposal.md` y `specs/foundation/spec.md`. El repositorio aún no tiene aplicaciones ni lockfiles. La referencia visual vive en `starter-design/Content Suite.dc.html` y la captura proporcionada confirma un dashboard operativo, azul, suave y con relieve físico.

## Goals / Non-Goals

**Goals:**
- Mantener una única autoridad de negocio en FastAPI dentro de un monorepo coordinado.
- Aislar los gestores de dependencias: npm para web y `uv` para API.
- Definir un shell web que conserve todas las secciones y patrones de `starter-design/` cuando se implementen en sus respectivas changes.
- Aumentar el claymorphism del diseño sin sacrificar legibilidad, estados semánticos ni contraste.

**Non-Goals:**
- No construir todas las pantallas de producto durante la foundation.
- No añadir un sistema de componentes amplio, microservicios ni una librería de animación sin una necesidad concreta.
- No convertir el HTML de `starter-design/` en código de producción.

## Decisions

### Monorepo coordinado, backend único
Turborepo orquestará las tareas de la raíz. npm workspaces será el grafo JavaScript de `apps/web`; `apps/api` seguirá su propio proyecto `uv` con `pyproject.toml` y `uv.lock`. Turbo coordina, pero no sustituye el gestor de dependencias ni separa la API en servicios.

Alternativa descartada: un workspace Python único en raíz. Añade configuración cruzada sin beneficio para una sola API.

### Dependencias verificadas y acotadas
Antes de añadir o actualizar cualquier dependencia, se consulta Context7 y se instala la versión estable actual compatible, actualizando el lockfile correspondiente. El backend usa exclusivamente `uv add`, `uv sync` y `uv run`.

Alternativa descartada: fijar versiones en documentos. Se desactualizarían antes de ejecutar la change y no reemplazan la verificación en el momento de instalación.

### Claymorphism como capa de materialidad
El frontend conservará la composición, navegación, métricas, estados y jerarquía de todas las secciones de `starter-design/`. Instalará `claymorphism-css` tras verificarlo con Context7 y aplicará `.clay` solo a superficies elevadas: sidebar, tarjetas principales, botones de acción, badges y paneles de estado. Tokens propios ajustarán `--clay-background`, radio, sombras interiores y exteriores para una materialidad azul más clara que la referencia.

La paleta canónica es: Strawberry Red `#E63946` para error y acciones destructivas; Honeydew `#F1FAEE` para canvas claro; Frosted Blue `#A8DADC` para superficies suaves e información; Steel Blue `#457B9D` para acciones secundarias y gráficos; y Deep Space Blue `#1D3557` para navegación, títulos y paneles profundos. No se añaden colores de marca fuera de esa paleta.

Las superficies de lectura, tablas, campos y contenido denso usarán una versión reducida del relieve para mantener contraste y escaneabilidad. Los estados semánticos conservarán verde, ámbar, rojo y azul con texto legible. No habrá sombras negras puras, gradientes AI por defecto ni clay en todos los elementos.

Alternativa descartada: recrear el efecto únicamente con sombras Tailwind. Clay CSS aporta la base pequeña y personalizable; los tokens del producto mantienen coherencia.

### Supabase MCP local con OAuth

Pi usará la extensión local `pi-supabase` para el endpoint oficial remoto, limitado al project ref indicado y a las funciones necesarias. El acceso queda en lectura/escritura para cubrir el desarrollo de foundation, pero cada herramienta con escritura solicita confirmación. La configuración local y cualquier material OAuth se ignoran en Git; la extensión guarda su token con permisos restringidos fuera del repositorio.

Alternativa descartada: incluir una clave de acceso en la configuración del repositorio. El flujo OAuth oficial no requiere secret estático y reduce la exposición.

### Movimiento con propósito
La foundation implementará solo feedback táctil y transiciones breves si son necesarios. Toda animación posterior seguirá `prefers-reduced-motion`, animará `transform` u `opacity`, y tendrá un propósito de feedback, jerarquía o transición de estado.

Alternativa descartada: animaciones decorativas perpetuas. Dañan la operatividad del dashboard y el rendimiento.

## Risks / Trade-offs

- [El efecto clay reduce contraste o convierte contenido denso en ruido] → Limitarlo a superficies elevadas, usar tokens semánticos y comprobar contraste WCAG AA.
- [La referencia contiene más UI que la change activa] → Usarla como autoridad visual global sin adelantar rutas, entidades ni flujos futuros.
- [Las tareas raíz no cubren una app Python] → Declarar scripts explícitos para `uv run` y verificar los comandos de raíz en la foundation.
- [Skills externas aportan reglas incompatibles con el producto] → `PROJECT_CONTEXT.md`, OpenSpec y `starter-design/` prevalecen sobre sus recomendaciones.

## Migration Plan

1. Crear los lockfiles y la configuración de tareas durante la implementación de esta change.
2. Ejecutar checks de web y API desde sus gestores respectivos y desde las tareas de raíz.
3. Validar health, auth y migraciones en una base limpia.
4. Revisar desktop y móvil del shell implementado; ejecutar el detector de Impeccable una vez sobre los archivos UI cambiados.

No existe producción ni migración previa; revertir consiste en retirar la change no desplegada y sus configuraciones asociadas.
