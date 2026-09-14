import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "cn"
import { Slot } from "radix-ui"

/*
  Primitive Button source-owned (shadcn) tematizada para Content Suite: las
  variantes mapean a la materialidad clay aprobada (clay-cta, clay-inset,
  clay-chip) definida en src/index.css. El foco visible lo aporta la regla
  global `:focus-visible` (Steel Blue; Honeydew sobre superficies clay-cta);
  `clay-press` añade el press táctil solo en punteros finos y respeta
  reduced motion. Sin `transition: all` ni defaults genéricos de shadcn.
*/
const buttonVariants = cva(
  "inline-flex shrink-0 items-center justify-center gap-1.5 whitespace-nowrap font-semibold select-none disabled:pointer-events-none [&_svg]:pointer-events-none [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default: "clay clay-cta clay-press disabled:opacity-60",
        secondary: "clay clay-inset text-info-fg",
        outline:
          "rounded-lg border border-line bg-surface clay-press text-ink-muted",
        ghost: "rounded-md text-steel hover:text-ink disabled:opacity-40",
        destructive: "clay clay-chip clay-press text-danger-fg disabled:opacity-40",
      },
      size: {
        default: "px-5 py-2.5 text-sm",
        sm: "px-4.5 py-2.5 text-[13.5px]",
        lg: "px-5.5 py-3 text-sm",
        chip: "px-2.5 py-1.5 text-[11.5px]",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

function Button({
  className,
  variant = "default",
  size = "default",
  asChild = false,
  ...props
}: React.ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean
  }) {
  const Comp = asChild ? Slot.Root : "button"

  return (
    <Comp
      data-slot="button"
      data-variant={variant}
      data-size={size}
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  )
}

export { Button }
