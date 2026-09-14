import * as React from "react"
import { cn } from "cn"
import { Label as LabelPrimitive } from "radix-ui"

/*
  Primitive Label source-owned (shadcn) con la tipografía de labels aprobada
  para los formularios estructurados (Brand DNA).
*/
function Label({
  className,
  ...props
}: React.ComponentProps<typeof LabelPrimitive.Root>) {
  return (
    <LabelPrimitive.Root
      data-slot="label"
      className={cn(
        "block text-[12px] leading-none font-semibold text-ink-muted select-none peer-disabled:cursor-not-allowed peer-disabled:opacity-50",
        className
      )}
      {...props}
    />
  )
}

export { Label }
