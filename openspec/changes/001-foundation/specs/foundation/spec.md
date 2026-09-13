## Purpose

Proporciona una base ejecutable y verificable para Content Suite, con acceso autenticado, persistencia inicial y una experiencia web coherente antes de habilitar capacidades de negocio.

## ADDED Requirements

### Requirement: Desarrollo coordinado del repositorio
El repositorio SHALL permitir instalar, ejecutar, verificar y construir las aplicaciones web y API desde una interfaz de desarrollo coherente, preservando una única API como autoridad de dominio.

#### Scenario: Ejecución local de la foundation
- **WHEN** un desarrollador prepara el repositorio con los lockfiles vigentes y ejecuta las tareas documentadas
- **THEN** la aplicación web y la API quedan disponibles localmente sin requerir secretos de proveedores AI

### Requirement: API de salud y frontera de identidad
La API SHALL exponer comprobaciones de salud y rechazar solicitudes a la identidad actual que no aporten una identidad autenticada válida.

#### Scenario: Health checks disponibles
- **WHEN** un cliente consulta las rutas de salud
- **THEN** recibe una respuesta exitosa que distingue disponibilidad del proceso y disponibilidad de sus dependencias esenciales sin invocar modelos pagos

#### Scenario: Identidad no autenticada
- **WHEN** un cliente sin una identidad válida consulta el recurso de identidad actual
- **THEN** la API responde con un error de autenticación y no expone un perfil

### Requirement: Base de membresías y roles
El sistema SHALL persistir perfiles, marcas y membresías con roles, y SHALL comprobar que un usuario pertenece a la marca antes de autorizar una acción de marca.

#### Scenario: Membresía válida
- **WHEN** un usuario autenticado con una membresía y rol permitidos solicita una acción de su marca
- **THEN** la política de autorización permite la acción

#### Scenario: Membresía inválida
- **WHEN** un usuario sin membresía o con rol no permitido solicita una acción de marca
- **THEN** la política rechaza la acción sin modificar estado

### Requirement: Shell web consistente con la guía visual
La aplicación web SHALL proporcionar un shell protegido, una navegación por rol y estados de carga, vacío y error mínimos. Toda pantalla o sección implementada SHALL conservar la jerarquía, los componentes y el lenguaje visual de `starter-design/`, con una materialidad claymorphism azul más pronunciada. Los tokens SHALL derivar exclusivamente de Strawberry Red `#E63946`, Honeydew `#F1FAEE`, Frosted Blue `#A8DADC`, Steel Blue `#457B9D` y Deep Space Blue `#1D3557`.

#### Scenario: Shell protegido disponible
- **WHEN** un usuario autenticado abre la aplicación web
- **THEN** ve navegación y contenido base acordes a su rol, y la web puede mostrar el estado de salud de la API

#### Scenario: Estado de interfaz no ideal
- **WHEN** la aplicación está cargando, no tiene datos o la API falla
- **THEN** presenta un estado comprensible que conserva la jerarquía y accesibilidad visual del shell

### Requirement: Fundación limitada al alcance acordado
La foundation SHALL entregar únicamente infraestructura, fronteras de identidad, persistencia inicial y shell web. No SHALL habilitar generación AI, Brand DNA, RAG, workflows de revisión ni auditoría visual.

#### Scenario: Límites de la entrega
- **WHEN** se verifica el árbol y las rutas de la foundation
- **THEN** no existen flujos productivos de las capacidades fuera de alcance
