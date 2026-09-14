import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "cn"

/*
  Primitive Badge source-owned (shadcn): estados semánticos derivados
  exclusivamente de la paleta canónica (tokens de index.css). Pastilla con
  relieve mínimo (`clay-badge`). `deep` es el estado activo de la referencia
  (Honeydew + Deep Space Blue).
*/
const badgeVariants = cva(
  "clay-badge inline-flex w-fit shrink-0 items-center gap-1.5 px-3 py-1 text-[11.5px] font-semibold whitespace-nowrap",
  {
    variants: {
      variant: {
        neutral: "bg-tint-steel text-info-fg",
        success: "bg-success-bg text-success-fg",
        info: "bg-info-bg text-info-fg",
        warning: "bg-warning-bg text-warning-fg",
        danger: "bg-danger-bg text-danger-fg",
        deep: "bg-honeydew text-deep",
      },
      size: {
        default: "",
        sm: "gap-1 px-2.5 py-0.5 text-[11px]",
      },
    },
    defaultVariants: {
      variant: "neutral",
      size: "default",
    },
  }
)

function Badge({
  className,
  variant,
  size,
  ...props
}: React.ComponentProps<"span"> & VariantProps<typeof badgeVariants>) {
  return (
    <span
      data-slot="badge"
      data-variant={variant}
      className={cn(badgeVariants({ variant, size }), className)}
      {...props}
    />
  )
}

export { Badge }
export type BadgeVariant = NonNullable<VariantProps<typeof badgeVariants>["variant"]>
