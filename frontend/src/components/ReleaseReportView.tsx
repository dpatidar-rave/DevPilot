import type { ReactNode } from 'react'

import type { ReleaseAssessment } from '@/services/api'

const READINESS_LABEL = {
  blocked: 'Blocked',
  needs_review: 'Needs review',
  ready_for_human_approval: 'Ready for human approval',
} as const

const STATUS_LABEL = {
  pending: 'Pending',
  passed: 'Passed',
  failed: 'Failed',
  waived: 'Waived',
  not_applicable: 'Not applicable',
} as const

export function ReleaseReportView({ report }: { report: ReleaseAssessment }) {
  return (
    <div className="space-y-8">
      <section>
        <p className="text-xs font-medium uppercase tracking-[0.14em] text-primary">Readiness</p>
        <h2 className="mt-2 font-serif text-3xl">{READINESS_LABEL[report.readiness]}</h2>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-muted-foreground">{report.statement}</p>
      </section>
      <Section title="Git">
        <dl className="grid gap-2 text-sm sm:grid-cols-2">
          <Fact label="Repository" value={report.project_name} />
          <Fact label="Base" value={report.base_ref || 'unknown'} />
          <Fact label="Reviewed commit" value={report.head_sha || 'missing'} />
          <Fact label="Repository HEAD" value={report.repository_head_sha || 'missing'} />
          <Fact label="Uncommitted changes" value={report.dirty ? 'yes' : 'no'} />
          <Fact label="Generated" value={report.generated_at} />
        </dl>
      </Section>
      <Section title="Model and review configuration">
        <dl className="grid gap-2 text-sm sm:grid-cols-2">
          <Fact label="Review" value={report.review_id} />
          <Fact label="Review status" value={report.review_status} />
          <Fact label="Model" value={report.model.name} />
          <Fact label="Context length" value={String(report.model.context_length)} />
          <Fact label="Temperature" value={String(report.model.temperature)} />
          <Fact label="Max output tokens" value={String(report.model.max_output_tokens)} />
          <Fact label="Timeout seconds" value={String(report.model.timeout_seconds)} />
        </dl>
      </Section>
      <Section title="Blockers">
        <BulletList items={report.blockers} />
      </Section>
      <Section title="Warnings">
        <BulletList items={report.warnings} />
      </Section>
      <Section title="Passed checks">
        <BulletList items={report.passed} />
      </Section>
      <Section title="Waivers">
        {report.waivers.length === 0 ? (
          <p className="text-sm text-muted-foreground">None.</p>
        ) : (
          <ul className="space-y-3">
            {report.waivers.map((item) => (
              <li key={`${item.text}-${item.reviewer}`} className="text-sm">
                <p className="font-medium">Waived — {item.text}</p>
                <p className="mt-1 text-muted-foreground">
                  Reason: {item.reason || 'none'}. Reviewer: {item.reviewer || 'none'}. A waiver is not a pass.
                </p>
              </li>
            ))}
          </ul>
        )}
      </Section>
      <Section title="Missing evidence">
        <BulletList items={report.missing} />
      </Section>
      <Section title="Checklist">
        <ul className="divide-y divide-border rounded-lg border border-border">
          {report.checklist.map((item) => (
            <li key={item.key} className="px-4 py-3 text-sm">
              <p>
                <span className="font-medium">{STATUS_LABEL[item.status]}</span>
                {' — '}
                {item.label}
              </p>
              <p className="mt-1 text-muted-foreground">{item.evidence}</p>
              {(item.reason || item.reviewer) && (
                <p className="mt-1 text-muted-foreground">
                  Reason: {item.reason || 'none'}. Reviewer: {item.reviewer || 'none'}.
                </p>
              )}
            </li>
          ))}
        </ul>
      </Section>
      <Section title="Findings">
        {report.findings.length === 0 ? (
          <p className="text-sm text-muted-foreground">None.</p>
        ) : (
          <ul className="space-y-3">
            {report.findings.map((item) => (
              <li key={item.id} className="text-sm">
                <p>
                  {item.severity}: {item.title} ({item.file_path}) — {item.decision || 'unresolved'}
                </p>
                {(item.reason || item.reviewer) && (
                  <p className="mt-1 text-muted-foreground">
                    Reason: {item.reason || 'none'}. Reviewer: {item.reviewer || 'none'}.
                  </p>
                )}
              </li>
            ))}
          </ul>
        )}
      </Section>
    </div>
  )
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section>
      <h2 className="font-serif text-2xl">{title}</h2>
      <div className="mt-3">{children}</div>
    </section>
  )
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="font-medium">{value}</dd>
    </div>
  )
}

function BulletList({ items }: { items: string[] }) {
  if (items.length === 0) {
    return <p className="text-sm text-muted-foreground">None.</p>
  }
  return (
    <ul className="list-disc space-y-1 pl-5 text-sm">
      {items.map((item) => (
        <li key={item}>{item}</li>
      ))}
    </ul>
  )
}
