## Purpose

Permite a un usuario real autenticarse en Content Suite mediante un login de producción respaldado por Supabase Auth, sin depender de tokens de desarrollo precodificados.

## ADDED Requirements

### Requirement: Login por magic link en producción
La aplicación web SHALL ofrecer, fuera de builds de desarrollo, un formulario de login que envíe un enlace mágico (magic link) por email a través de Supabase Auth como único mecanismo de entrada.

#### Scenario: Solicitud de magic link
- **WHEN** un usuario sin sesión activa ingresa su email en el formulario de login y lo envía
- **THEN** la aplicación solicita a Supabase Auth el envío de un magic link a ese email y muestra una confirmación sin revelar si el email tiene o no una cuenta existente

#### Scenario: Confirmación del magic link
- **WHEN** el usuario abre el enlace recibido y vuelve a la aplicación
- **THEN** la aplicación establece una sesión autenticada usando el token que Supabase Auth emite, sin requerir contraseña

### Requirement: Sesión persiste y se renueva sin intervención
La sesión establecida SHALL sobrevivir a una recarga de página mientras el token de refresco siga siendo válido, y el token de acceso SHALL renovarse antes de expirar sin exigir que el usuario vuelva a autenticarse.

#### Scenario: Recarga de página con sesión válida
- **WHEN** un usuario con una sesión de Supabase Auth vigente recarga la aplicación
- **THEN** la aplicación restablece la sesión automáticamente y el usuario permanece autenticado sin ver el formulario de login

#### Scenario: Renovación antes de expirar
- **WHEN** el token de acceso de la sesión activa se acerca a su expiración
- **THEN** la aplicación lo renueva usando el token de refresco antes de que una request a la API sea rechazada por expiración

### Requirement: Cierre de sesión explícito
La aplicación SHALL permitir cerrar la sesión activa de forma explícita, invalidando el token localmente y devolviendo al usuario al formulario de login.

#### Scenario: Usuario cierra sesión
- **WHEN** un usuario autenticado selecciona cerrar sesión
- **THEN** la aplicación descarta la sesión de Supabase Auth, deja de adjuntar el token a las requests de la API y muestra el formulario de login

### Requirement: Convivencia con identidades de desarrollo
En builds de desarrollo (`DEV`), la aplicación SHALL seguir ofreciendo el selector de identidades de desarrollo existente junto al login real, sin que uno reemplace al otro.

#### Scenario: Build de desarrollo con mapping de tokens
- **WHEN** la aplicación corre en un build de desarrollo y existe al menos un token de identidad de desarrollo configurado
- **THEN** la pantalla de login muestra tanto el formulario de login real como los accesos rápidos de identidad de desarrollo

#### Scenario: Build de producción
- **WHEN** la aplicación corre en un build de producción
- **THEN** la pantalla de login muestra únicamente el formulario de login real, sin ningún acceso de identidad de desarrollo
