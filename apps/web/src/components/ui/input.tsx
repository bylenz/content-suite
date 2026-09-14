import * as React from "react"
import { cn } from "cn"

/*
  Primitive Input source-owned (shadcn) con el estilo aprobado de los
  formularios: campo hundido en el lienzo (`clay-field`), sin borde duro, para
  preservar legibilidad dentro de la materialidad clay. El foco visible lo aporta la
  regla global `:focus-visible` de index.css.
*/
function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  return (
    <input
      type={type}
      data-slot="input"
      className={cn(
        "clay-field w-full min-w-0 border-0 px-3.5 py-2.5 text-[13.5px] text-ink placeholder:text-ink-soft disabled:cursor-not-allowed disabled:opacity-50",
        className
      )}
      {...props}
    />
  )
}

export { Input }
