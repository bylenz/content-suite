/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base URL de la API FastAPI. Por defecto http://localhost:8000 */
  readonly VITE_API_URL?: string
  /** URL del proyecto Supabase (Project Settings -> API) */
  readonly VITE_SUPABASE_URL?: string
  /** Publishable/anon key del proyecto Supabase (Project Settings -> API) */
  readonly VITE_SUPABASE_ANON_KEY?: string
  /** Mapping ignorado rol -> token de dev (solo builds de desarrollo) */
  readonly VITE_DEV_API_TOKEN_CREATOR?: string
  readonly VITE_DEV_API_TOKEN_CONTENT_REVIEWER?: string
  readonly VITE_DEV_API_TOKEN_VISUAL_REVIEWER?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
