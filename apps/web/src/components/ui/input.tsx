import * as React from "react"
import { cn } from "cn"

/*
  Primitive Input source-owned (shadcn) con el estilo aprobado de los
  formularios: relieve reducido (borde línea, fondo blanco), sin materialidad
  clay completa para preservar legibilidad. El foco visible lo aporta la
  regla global `:focus-visible` de index.css.
*/
function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  return (
    <input
      type={type}
      data-slot="input"
      className={cn(
        "w-full min-w-0 rounded-lg border border-line bg-white px-3 py-2 text-[13.5px] text-ink placeholder:text-ink-soft focus:border-steel disabled:cursor-not-allowed disabled:opacity-50",
        className
      )}
      {...props}
    />
  )
}

export { Input }
