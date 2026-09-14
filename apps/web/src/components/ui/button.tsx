import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "cn"
import { Slot } from "radix-ui"

/*
  Primitive Button source-owned (shadcn) tematizada para Content Suite: las
  variantes mapean a la materialidad clay (clay-cta con labio 3D, clay-tile
  elevado para la acción secundaria, clay-chip para outline/destructive)
  definida en src/index.css. El foco visible lo aporta la regla
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
        secondary: "clay clay-tile clay-press text-info-fg disabled:opacity-60",
        outline: "clay clay-chip clay-press text-ink-muted disabled:opacity-50",
        ghost:
          "rounded-[12px] text-steel transition-colors hover:bg-tint-steel hover:text-ink disabled:opacity-40",
        destructive: "clay clay-chip clay-press text-danger-fg disabled:opacity-40",
      },
      size: {
        default: "px-5 py-2.5 text-sm",
        sm: "px-4 py-2 text-[13px]",
        lg: "px-6 py-3.5 text-[15px]",
        chip: "px-3 py-1.5 text-[11.5px]",
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
