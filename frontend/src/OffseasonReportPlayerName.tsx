import { buildOffseasonPlayerReport } from './offseasonPlayerReport'

type Props = {
  saveState: any
  userTeam: string
  playerName: string
  className?: string
  onOpen: (playerName: string) => void
}

/** Single-click name link when an offseason growth report exists for this player. */
export default function OffseasonReportPlayerName({
  saveState,
  userTeam,
  playerName,
  className = '',
  onOpen,
}: Props) {
  const name = String(playerName ?? '').trim()
  if (!name || name === '—') {
    return <span className={className}>{playerName ?? '—'}</span>
  }

  const report = buildOffseasonPlayerReport(saveState, userTeam, name)
  if (!report) {
    return <span className={className}>{name}</span>
  }

  return (
    <button
      type="button"
      className={`pos-report-name-btn ${className}`.trim()}
      title="View offseason growth report"
      onClick={(e) => {
        e.stopPropagation()
        onOpen(name)
      }}
    >
      {name}
    </button>
  )
}
