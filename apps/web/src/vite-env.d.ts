/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base URL de la API FastAPI. Por defecto http://localhost:8000 */
  readonly VITE_API_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
