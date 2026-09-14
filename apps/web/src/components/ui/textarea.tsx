import * as React from "react"
import { cn } from "cn"

/*
  Primitive Textarea source-owned (shadcn), mismo estilo de campo que Input
  (relieve reducido); la altura la define el atributo `rows` del llamador.
*/
function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        "w-full min-w-0 rounded-lg border border-line bg-white px-3 py-2 text-[13.5px] text-ink placeholder:text-ink-soft focus:border-steel disabled:cursor-not-allowed disabled:opacity-50",
        className
      )}
      {...props}
    />
  )
}

export { Textarea }
