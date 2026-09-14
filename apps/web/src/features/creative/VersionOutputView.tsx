import { Badge } from '@/components/ui/badge'
import type { CreativeOutput } from './types'

/**
 * Salida de una versión renderizada según su tipo (starter-design):
 * descripción e imagen como texto editorial; video script como secciones
 * heading/body. Read-only: la edición pasa por el VersionEditForm.
 */
export function VersionOutputView({ output }: { output: CreativeOutput }) {
  if (output.content !== null) {
    return <p className="whitespace-pre-line text-[14.5px] leading-7 text-ink">{output.content}</p>
  }
  return (
    <div className="flex flex-col gap-3">
      {(output.structured_sections ?? []).map((section) => (
        <div key={section.heading} className="clay clay-subtle px-4 py-3.5">
          <p className="text-[11px] font-bold tracking-wide text-steel">{section.heading}</p>
          <p className="mt-1.5 text-[13.5px] leading-relaxed text-ink-muted">{section.body}</p>
        </div>
      ))}
      {output.applied_rule_ids.length > 0 && (
        <p className="mt-1 text-[11.5px] text-ink-soft">
          <Badge variant="deep" size="sm">
            {output.applied_rule_ids.length} reglas aplicadas
          </Badge>
        </p>
      )}
    </div>
  )
}
