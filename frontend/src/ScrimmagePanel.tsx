import { useState } from 'react'
import './TeamHomePage.css'

type ScrimmageResult = {
  name: string
  completed?: boolean
  home: string
  away: string
  home_score: number
  away_score: number
  ot?: boolean
  team_stats?: Record<string, { rush_yards?: number; pass_yards?: number; touchdowns?: number; turnovers?: number; sacks?: number; interceptions?: number; fumbles?: number; third_down?: string; fourth_down?: string }>
  player_stats?: Array<{ player_name: string; team_name: string; pass_yds?: number; rush_yds?: number; rec_yds?: number; comp?: number; att?: number }>
}

type ScrimmageOpponent = {
  opponent: string
  user_home?: boolean
}

type Props = {
  currentStage: string
  scrimmages: ScrimmageResult[]
  opponents?: ScrimmageOpponent[]
  onSimulate?: () => Promise<void>
  onPlay?: () => Promise<void>
}

export default function ScrimmagePanel({ currentStage, scrimmages, opponents = [], onSimulate, onPlay }: Props) {
  const [simulating, setSimulating] = useState(false)
  const [playing, setPlaying] = useState(false)
  // Prefer the latest entry for this stage (avoids a stale first entry blocking the UI after re-sim / sync issues).
  const prevResult = [...scrimmages].reverse().find((s) => s.name === currentStage)
  const lastCompleted = scrimmages.filter((s) => s.completed !== false).pop()
  const scrimIdx = currentStage === 'Scrimmage 1' ? 0 : 1
  const opponentSlot = opponents[scrimIdx]
  const isCompleted = Boolean(prevResult && prevResult.completed !== false)

  return (
    <div className="teamhome-preseason-panelA teamhome-scrimmage-panel">
      <div className="teamhome-preseason-title">{currentStage}</div>
      <div className="teamhome-scrimmage-opponent">
        {opponentSlot?.opponent ? (
          opponentSlot.user_home ? (
            <>vs {opponentSlot.opponent} <span className="teamhome-scrimmage-location">(Home)</span></>
          ) : (
            <>@ {opponentSlot.opponent} <span className="teamhome-scrimmage-location">(Away)</span></>
          )
        ) : (
          <>vs Non-conference opponent <span className="teamhome-scrimmage-location">(TBD)</span></>
        )}
      </div>
      <div className="teamhome-preseason-sub" style={{ marginBottom: 12 }}>
        {opponentSlot?.opponent
          ? `Practice game ${opponentSlot.user_home ? 'vs' : 'at'} ${opponentSlot.opponent}. Score and stats are shown but not recorded in season standings.`
          : 'Practice game vs a non-conference opponent. Score and stats are shown but not recorded in season standings.'}
      </div>

      {lastCompleted && lastCompleted.name !== currentStage ? (
        <div className="teamhome-scrimmage-sub" style={{ marginBottom: 8, opacity: 0.85 }}>
          Earlier: {lastCompleted.name} — {lastCompleted.home} {lastCompleted.home_score}–{lastCompleted.away} {lastCompleted.away_score}
        </div>
      ) : null}

      {prevResult && prevResult.completed !== false ? (
        <div className="teamhome-scrimmage-result">
          <div className="teamhome-scrimmage-score">
            {prevResult.home} {prevResult.home_score} – {prevResult.away} {prevResult.away_score}
            {prevResult.ot ? ' (OT)' : ''}
          </div>
          {prevResult.team_stats && (
            <div className="teamhome-scrimmage-stats">
              {[prevResult.home, prevResult.away].map((team) => {
                const ts = prevResult.team_stats?.[team]
                if (!ts) return null
                const rush = ts.rush_yards ?? 0
                const pass = ts.pass_yards ?? 0
                const total = rush + pass
                return (
                  <div key={team} className="teamhome-scrimmage-team-stats">
                    <div className="teamhome-scrimmage-team-name">{team}</div>
                    <div className="teamhome-scrimmage-stat-row">
                      {total} total yds · {rush} rush · {pass} pass · {ts.touchdowns ?? 0} TD · {ts.turnovers ?? 0} TO
                    </div>
                    {(ts.third_down || ts.fourth_down) && (
                      <div className="teamhome-scrimmage-stat-row">
                        3rd: {ts.third_down ?? '—'} · 4th: {ts.fourth_down ?? '—'}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </div>
      ) : null}

      {!isCompleted ? (
        <div className="teamhome-scrimmage-options" style={{ marginTop: 12 }}>
          <div className="teamhome-scrimmage-options-label">Choose how to play:</div>
          <div className="teamhome-scrimmage-buttons">
            <button
              type="button"
              className="teamhome-scrimmage-btn teamhome-scrimmage-btn-play"
              disabled={playing || !onPlay}
              onClick={async () => {
                if (!onPlay) return
                setPlaying(true)
                try {
                  await onPlay()
                } finally {
                  setPlaying(false)
                }
              }}
            >
              {playing ? 'Loading…' : 'Play the Scrimmage'}
            </button>
            <button
              type="button"
              className="teamhome-scrimmage-btn teamhome-scrimmage-btn-sim"
              disabled={simulating || !onSimulate}
              onClick={async () => {
                if (!onSimulate) return
                setSimulating(true)
                try {
                  await onSimulate()
                } finally {
                  setSimulating(false)
                }
              }}
            >
              {simulating ? 'Simulating… (may take 30–60 sec)' : 'Simulate the Scrimmage'}
            </button>
          </div>
          <div className="teamhome-scrimmage-coming-soon">
            <em>Play the Scrimmage</em> lets you coach the game play-by-play.
          </div>
        </div>
      ) : (
        <div className="teamhome-preseason-stage" style={{ marginTop: 12 }}>
          Click Continue to advance.
        </div>
      )}
    </div>
  )
}
