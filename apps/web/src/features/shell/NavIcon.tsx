/** Iconos de navegación reconstruidos desde starter-design (solo trazos SVG). */
export function NavIcon({ id }: { id: string }) {
  const common = {
    width: 16,
    height: 16,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 2,
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
    'aria-hidden': true,
  }
  switch (id) {
    case 'dashboard':
      return (
        <svg {...common}>
          <rect x="3" y="3" width="7" height="7" rx="1.5" />
          <rect x="14" y="3" width="7" height="7" rx="1.5" />
          <rect x="3" y="14" width="7" height="7" rx="1.5" />
          <rect x="14" y="14" width="7" height="7" rx="1.5" />
        </svg>
      )
    case 'brand-dna':
      return (
        <svg {...common}>
          <path d="M12 2 L21 12 L12 22 L3 12 Z" />
        </svg>
      )
    case 'creative-studio':
      return (
        <svg {...common}>
          <rect x="3" y="3" width="18" height="18" rx="3" />
          <path d="M12 8v8M8 12h8" />
        </svg>
      )
    case 'approvals':
      return (
        <svg {...common}>
          <path d="M4 12l5 5L20 6" />
        </svg>
      )
    case 'brand-audit':
      return (
        <svg {...common}>
          <circle cx="10.5" cy="10.5" r="6.5" />
          <path d="M20 20l-5-5" />
        </svg>
      )
    case 'observability':
      return (
        <svg {...common}>
          <path d="M3 12h3l2-6 4 12 2-6h7" />
        </svg>
      )
    default:
      return null
  }
}
