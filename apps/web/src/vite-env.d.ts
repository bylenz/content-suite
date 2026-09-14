/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base URL de la API FastAPI. Por defecto http://localhost:8000 */
  readonly VITE_API_URL?: string
  /** URL del proyecto Supabase (Project Settings -> API) */
  readonly VITE_SUPABASE_URL?: string
  /** Publishable/anon key del proyecto Supabase (Project Settings -> API) */
  readonly VITE_SUPABASE_ANON_KEY?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
