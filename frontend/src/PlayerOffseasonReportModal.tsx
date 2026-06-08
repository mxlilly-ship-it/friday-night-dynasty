import type { OffseasonPlayerReport } from './offseasonPlayerReport'
import './PlayerOffseasonReportModal.css'

type Props = {
  report: OffseasonPlayerReport
  onClose: () => void
}

function fmtDelta(n: number) {
  return n >= 0 ? `+${n}` : String(n)
}

function ChangeRow({
  label,
  before,
  after,
  delta,
  base,
  equipment,
}: {
  label: string
  before?: number
  after?: number
  delta: number
  base?: number
  equipment?: number
}) {
  const hasSplit = (base ?? 0) > 0 || (equipment ?? 0) > 0
  return (
    <div className="pos-report-change-row">
      <span className="pos-report-change-label">{label}</span>
      <span className="pos-report-change-values">
        {before != null && after != null ? (
          <span className="pos-report-change-range">
            {before} → {after} ({fmtDelta(delta)})
          </span>
        ) : (
          <span className="pos-report-change-range">{fmtDelta(delta)}</span>
        )}
        {hasSplit ? (
          <span className="pos-report-change-split">
            {base ? `dev ${fmtDelta(base)}` : null}
            {base && equipment ? ' · ' : null}
            {equipment ? `equipment ${fmtDelta(equipment)}` : null}
          </span>
        ) : null}
      </span>
    </div>
  )
}

export default function PlayerOffseasonReportModal({ report, onClose }: Props) {
  return (
    <div
      className="pos-report-backdrop"
      role="presentation"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div className="pos-report-modal" role="dialog" aria-labelledby="pos-report-title">
        <div className="pos-report-header">
          <div>
            <h2 id="pos-report-title" className="pos-report-title">
              {report.playerName}
            </h2>
            <p className="pos-report-meta">
              {report.position} · {report.yearLabel}
              {report.ovr ? (
                <>
                  {' '}
                  · OVR {report.ovr.before} → {report.ovr.after} ({fmtDelta(report.ovr.delta)})
                </>
              ) : null}
            </p>
          </div>
          <button type="button" className="pos-report-close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>

        <div className="pos-report-body">
          <p className="pos-report-intro">Offseason growth by phase — winter, spring, and training results.</p>
          {report.sections.map((section) => (
            <section key={section.id} className="pos-report-section">
              <div className="pos-report-section-head">
                <h3 className="pos-report-section-title">{section.title}</h3>
                {section.subtitle ? <p className="pos-report-section-sub">{section.subtitle}</p> : null}
              </div>
              {section.changes.length > 0 ? (
                <div className="pos-report-changes">
                  {section.changes.map((c) => (
                    <ChangeRow
                      key={`${section.id}-${c.attr}`}
                      label={c.label}
                      before={c.before}
                      after={c.after}
                      delta={c.delta}
                      base={c.base}
                      equipment={c.equipment}
                    />
                  ))}
                </div>
              ) : (
                <p className="pos-report-empty">{section.emptyMessage ?? 'No changes recorded.'}</p>
              )}
            </section>
          ))}
        </div>
      </div>
    </div>
  )
}
