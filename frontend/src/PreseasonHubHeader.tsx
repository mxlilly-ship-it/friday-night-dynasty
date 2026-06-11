type Props = {
  seasonYear: number
  stages: string[]
  stageIndex: number
  formatStageLabel: (stage: string) => string
}

export default function PreseasonHubHeader({ seasonYear, stages, stageIndex, formatStageLabel }: Props) {
  const current = stages[stageIndex] ?? ''
  const total = stages.length
  const step = total ? Math.min(stageIndex + 1, total) : 0

  return (
    <header className="teamhome-preseason-hub-header" aria-label="Preseason progress">
      <p className="teamhome-preseason-hub-eyebrow">
        Preseason
        {Number.isFinite(seasonYear) ? ` · ${seasonYear}` : ''}
        {total ? ` · Step ${step} of ${total}` : ''}
      </p>
      <h1 className="teamhome-preseason-hub-title">{formatStageLabel(current || 'Preseason')}</h1>
      {total > 1 ? (
        <nav className="teamhome-preseason-stage-track" aria-label="Preseason stages">
          {stages.map((stage, i) => {
            const done = i < stageIndex
            const active = i === stageIndex
            const pillClass = [
              'teamhome-preseason-stage-pill',
              done ? 'teamhome-preseason-stage-pill--done' : '',
              active ? 'teamhome-preseason-stage-pill--active' : '',
            ]
              .filter(Boolean)
              .join(' ')
            return (
              <span
                key={`${stage}-${i}`}
                className={pillClass}
                aria-current={active ? 'step' : undefined}
                title={stage}
              >
                {formatStageLabel(stage)}
              </span>
            )
          })}
        </nav>
      ) : null}
    </header>
  )
}
