import * as React from "react"
import { cn } from "cn"

/*
  Primitive Card source-owned (shadcn) tematizada como superficie clay blanca
  elevada (`clay clay-card`) de la referencia. Las tarjetas densas de lectura
  siguen usando `.clay-subtle` directamente: relieve reducido, no Card.
*/
function Card({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="card"
      className={cn("clay clay-card text-sm text-ink", className)}
      {...props}
    />
  )
}

export { Card }
