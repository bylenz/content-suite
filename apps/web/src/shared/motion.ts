import type { Transition, Variants } from 'motion/react'

/**
 * Tokens de motion compartidos (espejo de --ease-soft/--duration-soft en
 * index.css). Solo opacidad y transform; duraciones < 300 ms e
 * interrumpibles. `MotionConfig reducedMotion="user"` (App.tsx) elimina el
 * movimiento posicional cuando el usuario lo solicita: las variantes no
 * necesitan distinguir reduced motion salvo las que animan fuera de motion
 * components.
 */
export const EASE_SOFT = [0.23, 1, 0.32, 1] as [number, number, number, number]

/**
 * Transición de entrada de superficie (entradas ocasionales de pantalla):
 * muelle corto y bien amortiguado, para que las tarjetas clay "asienten"
 * con un ligero rebote sin superar ~300 ms perceptibles.
 */
export const surfaceTransition: Transition = {
  type: 'spring',
  stiffness: 420,
  damping: 32,
  mass: 0.9,
}

/** Variante de opacidad de la entrada (sin muelle: la opacidad no rebota). */
export const surfaceFade: Transition = {
  duration: 0.2,
  ease: EASE_SOFT,
}

/** Crossfade breve para cambios de sección (solo opacidad). */
export const crossfadeTransition: Transition = {
  duration: 0.16,
  ease: 'easeOut',
}

/** Contenedor que escalona sus hijos directos al entrar. */
export const surfaceGroup: Variants = {
  hidden: {},
  show: {
    transition: { staggerChildren: 0.06, delayChildren: 0.04 },
  },
}

/**
 * Elemento de entrada: opacidad + desplazamiento vertical + escala mínima
 * (la superficie clay se "posa" sobre el lienzo).
 */
export const surfaceItem: Variants = {
  hidden: { opacity: 0, y: 16, scale: 0.98 },
  show: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: { ...surfaceTransition, opacity: surfaceFade },
  },
}

/** Tiles pequeños dentro de una tarjeta: entrada escalonada más rápida. */
export const tileGroup: Variants = {
  hidden: {},
  show: {
    transition: { staggerChildren: 0.04, delayChildren: 0.08 },
  },
}

export const tileItem: Variants = {
  hidden: { opacity: 0, y: 10, scale: 0.96 },
  show: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: { ...surfaceTransition, opacity: surfaceFade },
  },
}

/**
 * Elemento de feedback de estado (banners de publicación): opacidad y
 * desplazamiento mínimo, sin keyframes.
 */
export const feedbackItem: Variants = {
  hidden: { opacity: 0, y: 8, scale: 0.98 },
  show: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: { ...surfaceTransition, opacity: surfaceFade },
  },
  exit: { opacity: 0, y: 6, scale: 0.98, transition: crossfadeTransition },
}

/**
 * Contenido interior del drawer móvil: entra/sale horizontalmente. Se anima
 * solo el interior; el <dialog> nativo conserva Escape, foco y backdrop.
 */
export const drawerContent: Variants = {
  open: { opacity: 1, x: 0, transition: surfaceTransition },
  closing: { opacity: 0, x: -16, transition: crossfadeTransition },
  closed: { opacity: 0, x: -16 },
}
