## 1. Tooling del monorepo

- [x] 1.1 Crear `package.json`, configuración de npm workspaces y `turbo.json`; verificar que las tareas raíz descubren web y los comandos API declarados.
- [x] 1.2 Inicializar `apps/web` con Vite, React, TypeScript, Tailwind y dependencias verificadas con Context7; verificar instalación, lint, typecheck y build.
- [x] 1.3 Inicializar `apps/api` con `uv`, `pyproject.toml` y `uv.lock`; verificar `uv sync` y que todos los comandos Python funcionan con `uv run`.
- [x] 1.4 Instalar la extensión `pi-supabase` localmente, configurar su endpoint remoto con el project ref y features aprobados, e ignorar configuración y credenciales locales; verificar el descubrimiento de la extensión y la exclusión de Git.

## 2. Shell web

- [x] 2.1 Implementar app shell, ruta protegida, boundary de sesión y cliente API; verificar que la web muestra el estado de salud de la API.
- [x] 2.2 Instalar Clay CSS tras validarlo con Context7 y definir tokens de materialidad desde Strawberry Red `#E63946`, Honeydew `#F1FAEE`, Frosted Blue `#A8DADC`, Steel Blue `#457B9D` y Deep Space Blue `#1D3557`; verificar en desktop y móvil que las superficies elevadas siguen `starter-design/` con contraste accesible.
- [x] 2.3 Implementar estados mínimos de carga, vacío y error; verificar que conservan navegación por rol y jerarquía visual.

## 3. API y persistencia inicial

- [x] 3.1 Crear la aplicación FastAPI, configuración, CORS y rutas `/health/live` y `/health/ready`; verificar sus respuestas sin llamadas a proveedores AI.
- [x] 3.2 Implementar la dependencia de autenticación y el esqueleto de `/api/v1/me`; verificar que una identidad ausente o inválida recibe un error de autenticación.
- [x] 3.3 Crear modelos, Alembic y la primera migración para perfiles, marcas, membresías y roles; verificar que la migración aplica sobre una base limpia.
- [x] 3.4 Implementar políticas de membresía y rol; verificar los casos de permiso válido, membresía ausente y rol inválido.

## 4. Verificación y documentación

- [x] 4.1 Añadir pruebas de health, auth y políticas de membresía/rol; verificar `uv run pytest`.
- [x] 4.2 Añadir smoke test de frontend solo si el tooling lo soporta sin overhead excesivo; verificar el resultado o documentar la exclusión.
- [x] 4.3 Documentar comandos locales exactos, dependencias instaladas y versiones comprobadas con Context7; verificar tareas Turbo, build web, migración y conectividad web-API.
- [x] 4.4 Ejecutar una revisión visual desktop y móvil y el detector de Impeccable sobre los archivos UI modificados; verificar que los findings se resuelven o se registran como deuda explícita.
