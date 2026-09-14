import type { BrandDnaDocument, SectionKey } from '../../shared/api/types'
import { FIELD_LABELS, sectionTitle } from './sections'

/**
 * Vista editorial de una sección del documento operativo (no un blob Markdown).
 * Relieve reducido (clay-subtle) por ser contenido denso de lectura.
 */

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="eyebrow mb-1.5">{label}</p>
      <p className="text-[13.5px] leading-relaxed text-ink-muted">{value}</p>
    </div>
  )
}

function TagList({ items, tone = 'neutral' }: { items: string[]; tone?: 'neutral' | 'good' | 'bad' }) {
  const toneClass =
    tone === 'good'
      ? 'bg-success-bg text-success-fg'
      : tone === 'bad'
        ? 'bg-danger-bg text-danger-fg'
        : 'bg-tint-frosted text-ink'
  return (
    <div className="flex flex-wrap gap-2">
      {items.map((item) => (
        <span
          key={item}
          className={`rounded-[7px] px-2.5 py-1 text-[12.5px] font-semibold ${toneClass}`}
        >
          {item}
        </span>
      ))}
    </div>
  )
}

function Card({
  title,
  children,
}: {
  title: string
  children: React.ReactNode
}) {
  return (
    <section className="clay clay-subtle flex flex-col gap-4 p-6">
      <h3 className="text-[14px] font-bold text-ink">{title}</h3>
      {children}
    </section>
  )
}

function IdentityView({ document }: { document: BrandDnaDocument }) {
  const section = document.identity
  return (
    <Card title={sectionTitle('identity')}>
      <div className="grid gap-4 md:grid-cols-2">
        <Field label={FIELD_LABELS.identity.purpose} value={section.purpose} />
        <Field label={FIELD_LABELS.identity.positioning} value={section.positioning} />
      </div>
      <div>
        <p className="eyebrow mb-2">{FIELD_LABELS.identity.personality_traits}</p>
        <TagList items={section.personality_traits} />
      </div>
      <Field label={FIELD_LABELS.identity.audience} value={section.audience} />
    </Card>
  )
}

function VoiceView({ document }: { document: BrandDnaDocument }) {
  const section = document.voice
  return (
    <Card title={sectionTitle('voice')}>
      <div>
        <p className="eyebrow mb-2">{FIELD_LABELS.voice.tone_characteristics}</p>
        <TagList items={section.tone_characteristics} />
      </div>
      <Field label={FIELD_LABELS.voice.usage_guide} value={section.usage_guide} />
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <p className="eyebrow mb-2">{FIELD_LABELS.voice.preferred_vocabulary}</p>
          <TagList items={section.preferred_vocabulary} tone="good" />
        </div>
        <div>
          <p className="eyebrow mb-2">{FIELD_LABELS.voice.avoid_vocabulary}</p>
          <TagList items={section.avoid_vocabulary} tone="bad" />
        </div>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="rounded-[10px] bg-success-bg p-4">
          <p className="text-[11px] font-bold uppercase tracking-[0.05em] text-success-fg">Hacer</p>
          <ul className="mt-2 flex flex-col gap-2">
            {section.do_examples.map((example) => (
              <li key={example} className="text-[13px] italic leading-relaxed text-ink-muted">
                “{example}”
              </li>
            ))}
          </ul>
        </div>
        <div className="rounded-[10px] bg-danger-bg p-4">
          <p className="text-[11px] font-bold uppercase tracking-[0.05em] text-danger-fg">
            No hacer
          </p>
          <ul className="mt-2 flex flex-col gap-2">
            {section.dont_examples.map((example) => (
              <li key={example} className="text-[13px] italic leading-relaxed text-ink-muted">
                “{example}”
              </li>
            ))}
          </ul>
        </div>
      </div>
    </Card>
  )
}

function CommunicationView({ document }: { document: BrandDnaDocument }) {
  const section = document.communication
  return (
    <Card title={sectionTitle('communication')}>
      <div className="flex flex-col gap-3">
        {section.message_pillars.map((pillar) => (
          <div key={pillar.name} className="rounded-[9px] bg-tint-steel px-4 py-3">
            <p className="text-[13.5px] font-semibold text-ink">{pillar.name}</p>
            <p className="mt-1 text-[13px] leading-relaxed text-ink-muted">{pillar.description}</p>
          </div>
        ))}
      </div>
      <div>
        <p className="eyebrow mb-2">{FIELD_LABELS.communication.rules}</p>
        <ul className="flex flex-col gap-2">
          {section.rules.map((rule) => (
            <li key={rule} className="flex items-start gap-2 text-[13.5px] text-ink-muted">
              <span aria-hidden="true" className="mt-0.5 font-bold text-success-fg">
                +
              </span>
              {rule}
            </li>
          ))}
        </ul>
      </div>
    </Card>
  )
}

function VisualRulesView({ document }: { document: BrandDnaDocument }) {
  const section = document.visual_rules
  return (
    <Card title={sectionTitle('visual_rules')}>
      <div className="grid gap-4 md:grid-cols-2">
        <Field label={FIELD_LABELS.visual_rules.visual_personality} value={section.visual_personality} />
        <Field label={FIELD_LABELS.visual_rules.imagery_direction} value={section.imagery_direction} />
        <Field label={FIELD_LABELS.visual_rules.composition} value={section.composition} />
        <Field label={FIELD_LABELS.visual_rules.logo_usage} value={section.logo_usage} />
      </div>
    </Card>
  )
}

function RestrictionsView({ document }: { document: BrandDnaDocument }) {
  return (
    <Card title={sectionTitle('restrictions')}>
      <ul className="flex flex-col gap-2">
        {document.restrictions.rules.map((rule) => (
          <li key={rule} className="flex items-start gap-2 text-[13.5px] text-ink-muted">
            <span aria-hidden="true" className="mt-0.5 font-bold text-danger-fg">
              −
            </span>
            {rule}
          </li>
        ))}
      </ul>
    </Card>
  )
}

const SECTION_VIEWS: Record<SectionKey, (props: { document: BrandDnaDocument }) => React.JSX.Element> = {
  identity: IdentityView,
  voice: VoiceView,
  communication: CommunicationView,
  visual_rules: VisualRulesView,
  restrictions: RestrictionsView,
}

export function DocumentSectionView({
  section,
  document,
}: {
  section: SectionKey
  document: BrandDnaDocument
}) {
  const View = SECTION_VIEWS[section]
  return <View document={document} />
}
