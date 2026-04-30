import { useMemo, useState } from 'react'
import './ScoutingReportPage.css'
import TeamLogo from './TeamLogo'
import { buildScoutingReportBundle } from './scoutingReportEngine'
import type { ScoutingReportBundle } from './scoutingReportTypes'

const MENU_OFF = 'Offensive Scouting Report'
const MENU_DEF = 'Defensive Scouting Report'

export { MENU_OFF as SCOUTING_MENU_OFFENSE, MENU_DEF as SCOUTING_MENU_DEFENSE }

type Props = {
  apiBase: string
  headers: Record<string, string>
  saveState: any
  userTeam: string
  initialTab: 'offense' | 'defense'
  logoVersion?: number
  onBack: () => void
}

function ChipList({ title, icon, items, tone }: { title: string; icon: string; items: string[]; tone: 'good' | 'bad' | 'neutral' }) {
  if (!items.length) return null
  return (
    <section className={`scouting-card scouting-card--${tone}`}>
      <h3 className="scouting-card-title">
        <span className="scouting-card-icon" aria-hidden>
          {icon}
        </span>
        {title}
      </h3>
      <ul className="scouting-chip-list">
        {items.map((t) => (
          <li key={t} className="scouting-chip">
            {t}
          </li>
        ))}
      </ul>
    </section>
  )
}

function MatchupList({ title, lines }: { title: string; lines: { arrow: string; position: string; player: string; reason: string }[] }) {
  if (!lines.length) return null
  return (
    <section className="scouting-card scouting-card--neutral">
      <h3 className="scouting-card-title">{title}</h3>
      <ul className="scouting-matchup-list">
        {lines.map((l, i) => (
          <li key={`${l.player}-${i}`} className="scouting-matchup">
            <span className="scouting-matchup-arrow" aria-hidden>
              {l.arrow === 'attack' ? '→' : l.arrow === 'avoid' ? '⇢' : '■'}
            </span>
            <div>
              <div className="scouting-matchup-head">
                {l.position} · <strong>{l.player}</strong>
              </div>
              <div className="scouting-matchup-reason">{l.reason}</div>
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}

function OpponentScheduleList({
  rows,
}: {
  rows: { opponent: string; result: 'W' | 'L'; opponentWins: number; opponentLosses: number }[]
}) {
  if (!rows.length) return null
  return (
    <section className="scouting-card scouting-card--neutral">
      <h3 className="scouting-card-title">Opponent schedule</h3>
      <ul className="scouting-opponent-list">
        {rows.map((row, idx) => (
          <li key={`${row.opponent}-${idx}`} className="scouting-opponent-row">
            <span className={`scouting-opponent-result ${row.result === 'W' ? 'win' : 'loss'}`}>{row.result}</span>
            <span className="scouting-opponent-name">{row.opponent}</span>
            <span className="scouting-opponent-record">
              {row.opponentWins}-{row.opponentLosses}
            </span>
          </li>
        ))}
      </ul>
      <p className="scouting-fine">Recent opponents and current opponent records.</p>
    </section>
  )
}

function QuickList({ title, rows }: { title: string; rows: string[] }) {
  if (!rows.length) return null
  return (
    <section className="scouting-card scouting-card--neutral">
      <h3 className="scouting-card-title">{title}</h3>
      <ul className="scouting-form-list">
        {rows.map((r, i) => (
          <li key={`${r}-${i}`}>{r}</li>
        ))}
      </ul>
    </section>
  )
}

function LastWeekBoxScoreCard({
  box,
}: {
  box: { opponent: string; result: 'W' | 'L'; score: string; notes: string[] } | null
}) {
  if (!box) return null
  return (
    <section className="scouting-card scouting-card--neutral">
      <h3 className="scouting-card-title">Last week box score glance</h3>
      <p className="scouting-big">
        {box.result} vs {box.opponent} · {box.score}
      </p>
      <ul className="scouting-form-list">
        {box.notes.map((n, i) => (
          <li key={`${n}-${i}`}>{n}</li>
        ))}
      </ul>
    </section>
  )
}

export default function ScoutingReportPage({ apiBase, headers, saveState, userTeam, initialTab, logoVersion, onBack }: Props) {
  const teamNames = useMemo(() => {
    const names = (saveState?.teams ?? []).map((t: any) => String(t?.name ?? '')).filter(Boolean)
    return [...names].sort((a, b) => a.localeCompare(b))
  }, [saveState?.teams])

  const [selectedTeam, setSelectedTeam] = useState(() => (userTeam && teamNames.includes(userTeam) ? userTeam : teamNames[0] ?? ''))
  const [tab, setTab] = useState<'offense' | 'defense'>(initialTab)

  const bundle: ScoutingReportBundle | null = useMemo(() => {
    if (!selectedTeam) return null
    return buildScoutingReportBundle(saveState, selectedTeam)
  }, [saveState, selectedTeam])

  const side = tab === 'offense' ? bundle?.offense : bundle?.defense

  return (
    <div className="scouting-report scouting-report-print">
      <div className="scouting-toolbar no-print">
        <button type="button" className="scouting-back" onClick={onBack}>
          ← Team Home
        </button>
        <div className="scouting-toolbar-actions">
          <button type="button" className="scouting-btn" onClick={() => window.print()}>
            Print report
          </button>
        </div>
      </div>

      <header className="scouting-header">
        <div className="scouting-header-logo">
          <TeamLogo apiBase={apiBase} headers={headers} teamName={selectedTeam} logoVersion={logoVersion} size={72} />
        </div>
        <div className="scouting-header-text">
          <div className="scouting-kicker">Scouting department</div>
          <h1 className="scouting-title">Game plan brief — {selectedTeam || 'Select team'}</h1>
          <div className="scouting-meta">
            <span>{bundle?.offense.schoolTypeLabel ?? '—'} program</span>
            <span className="scouting-meta-dot">·</span>
            <span>{bundle?.offense.classification ?? '—'}</span>
            {bundle ? (
              <>
                <span className="scouting-meta-dot">·</span>
                <span>
                  Confidence: <strong>{bundle.offense.confidence}</strong> ({bundle.gamesSampled} games sampled)
                </span>
                <span className="scouting-meta-dot">·</span>
                <span>
                  Staff sharpness: <strong>{Math.round(bundle.offense.reportSharpness * 100)}%</strong>
                </span>
              </>
            ) : null}
          </div>
        </div>
      </header>

      <div className="scouting-controls no-print">
        <label className="scouting-field">
          <span className="scouting-field-label">Scout team</span>
          <select className="scouting-select" value={selectedTeam} onChange={(e) => setSelectedTeam(e.target.value)}>
            {teamNames.map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </label>
        <div className="scouting-tabs" role="tablist">
          <button
            type="button"
            role="tab"
            aria-selected={tab === 'offense'}
            className={`scouting-tab ${tab === 'offense' ? 'active' : ''}`}
            onClick={() => setTab('offense')}
          >
            Offense
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={tab === 'defense'}
            className={`scouting-tab ${tab === 'defense' ? 'active' : ''}`}
            onClick={() => setTab('defense')}
          >
            Defense
          </button>
        </div>
      </div>

      {!bundle || !side ? (
        <div className="scouting-empty">Load a save with teams to generate scouting.</div>
      ) : (
        <>
          <p className="scouting-confidence-note">{side.confidenceNote}</p>

          {tab === 'offense' ? (
            <div className="scouting-grid">
              <section className="scouting-card scouting-card--neutral scouting-span-2">
                <h3 className="scouting-card-title">Team identity</h3>
                <div className="scouting-identity">
                  <div>
                    <div className="scouting-label">Playbook</div>
                    <div className="scouting-value">{bundle.offense.identity.playbook}</div>
                  </div>
                  <div>
                    <div className="scouting-label">Philosophy</div>
                    <div className="scouting-value">{bundle.offense.identity.philosophy}</div>
                  </div>
                  <div>
                    <div className="scouting-label">Spring emphasis</div>
                    <div className="scouting-value">{bundle.offense.identity.springOffenseFocus}</div>
                  </div>
                </div>
              </section>

              <section className="scouting-card scouting-card--neutral">
                <h3 className="scouting-card-title">Run / pass tilt</h3>
                <p className="scouting-big">
                  {bundle.offense.runPass.runPct}% run-weighted · {bundle.offense.runPass.passPct}% pass-weighted
                </p>
                <p className="scouting-fine">{bundle.offense.runPass.note}</p>
              </section>

              <section className="scouting-card scouting-card--neutral">
                <h3 className="scouting-card-title">Pace</h3>
                <p className="scouting-big">
                  {bundle.offense.pace.label.charAt(0).toUpperCase() + bundle.offense.pace.label.slice(1)}
                </p>
                <p className="scouting-fine">~{bundle.offense.pace.playsPerGame} plays / game (offense sample)</p>
              </section>

              <section className="scouting-card scouting-card--neutral scouting-span-2">
                <h3 className="scouting-card-title">Play caller profile</h3>
                <div className="scouting-pills">
                  {bundle.offense.playCallerType.map((t) => (
                    <span key={t} className="scouting-pill">
                      {t}
                    </span>
                  ))}
                </div>
              </section>

              <section className="scouting-card scouting-card--neutral scouting-span-2">
                <h3 className="scouting-card-title">Recent form</h3>
                <ul className="scouting-form-list">
                  <li>
                    <span className="scouting-label">Big wins</span> {bundle.offense.recentForm.bigWins}
                  </li>
                  <li>
                    <span className="scouting-label">Tough losses</span> {bundle.offense.recentForm.toughLosses}
                  </li>
                  <li>
                    <span className="scouting-label">Last game</span> {bundle.offense.recentForm.lastGame}
                  </li>
                </ul>
              </section>

              <OpponentScheduleList rows={bundle.offense.opponentSchedule} />
              <LastWeekBoxScoreCard box={bundle.offense.lastWeekBoxScore} />
              <QuickList title="Game plan recommendations" rows={bundle.offense.gameplanRecommendations} />

              <ChipList title="Strengths" icon="✔" items={bundle.offense.strengths} tone="good" />
              <ChipList title="Weaknesses" icon="✖" items={bundle.offense.weaknesses} tone="bad" />

              <div className="scouting-span-2 scouting-split">
                <MatchupList title="Who to attack" lines={bundle.offense.whoToAttack} />
                <MatchupList title="Who to stop" lines={bundle.offense.whoToStop} />
              </div>

              <section className="scouting-card scouting-card--neutral scouting-span-2">
                <h3 className="scouting-card-title">Key players</h3>
                <div className="scouting-key-grid">
                  {bundle.offense.keyPlayers.map((kp) => (
                    <div key={`${kp.role}-${kp.name}`} className="scouting-key-card">
                      <div className="scouting-key-role">{kp.role}</div>
                      <div className="scouting-key-name">
                        {kp.name} <span className="scouting-pos">({kp.position})</span>
                      </div>
                      <div className="scouting-key-tag">{kp.tag}</div>
                    </div>
                  ))}
                </div>
              </section>

              <section className="scouting-card scouting-card--neutral scouting-span-2">
                <h3 className="scouting-card-title">Situational tendencies</h3>
                <ul className="scouting-tendency-list">
                  {bundle.offense.tendencies.map((row) => (
                    <li key={row.situation}>
                      <span className="scouting-tendency-sit">{row.situation}</span>
                      <span className="scouting-tendency-lbl">{row.label}</span>
                    </li>
                  ))}
                </ul>
              </section>

              <section className="scouting-card scouting-card--summary scouting-span-2">
                <h3 className="scouting-card-title">Assistant coach summary</h3>
                <p className="scouting-summary-text">{bundle.offense.assistantSummary}</p>
              </section>
            </div>
          ) : (
            <div className="scouting-grid">
              <section className="scouting-card scouting-card--neutral scouting-span-2">
                <h3 className="scouting-card-title">Defensive identity</h3>
                <div className="scouting-identity">
                  <div>
                    <div className="scouting-label">Playbook</div>
                    <div className="scouting-value">{bundle.defense.identity.playbook}</div>
                  </div>
                  <div>
                    <div className="scouting-label">Philosophy</div>
                    <div className="scouting-value">{bundle.defense.identity.philosophy}</div>
                  </div>
                  <div>
                    <div className="scouting-label">Spring emphasis</div>
                    <div className="scouting-value">{bundle.defense.identity.springDefenseFocus}</div>
                  </div>
                </div>
              </section>

              <section className="scouting-card scouting-card--neutral">
                <h3 className="scouting-card-title">Blitz frequency</h3>
                <p className="scouting-big">{bundle.defense.blitzFrequency.toUpperCase()}</p>
                <p className="scouting-fine">Derived from coordinator philosophy + style tags</p>
              </section>

              <section className="scouting-card scouting-card--neutral">
                <h3 className="scouting-card-title">Coverage tilt</h3>
                <p className="scouting-fine">{bundle.defense.coverageTilt}</p>
              </section>

              <OpponentScheduleList rows={bundle.defense.opponentSchedule} />
              <LastWeekBoxScoreCard box={bundle.defense.lastWeekBoxScore} />
              <QuickList title="Game plan recommendations" rows={bundle.defense.gameplanRecommendations} />

              <ChipList title="Strengths" icon="✔" items={bundle.defense.strengths} tone="good" />
              <ChipList title="Weaknesses" icon="✖" items={bundle.defense.weaknesses} tone="bad" />

              <div className="scouting-span-2 scouting-split">
                <MatchupList title="Who to attack" lines={bundle.defense.whoToAttack} />
                <MatchupList title="Who to avoid" lines={bundle.defense.whoToAvoid} />
              </div>

              <section className="scouting-card scouting-card--neutral scouting-span-2">
                <h3 className="scouting-card-title">Pressure & coverage by situation</h3>
                <ul className="scouting-tendency-list">
                  {bundle.defense.pressureByDown.map((row) => (
                    <li key={row.situation}>
                      <span className="scouting-tendency-sit">{row.situation}</span>
                      <span className="scouting-tendency-lbl">{row.label}</span>
                    </li>
                  ))}
                </ul>
              </section>

              <section className="scouting-card scouting-card--summary scouting-span-2">
                <h3 className="scouting-card-title">Assistant coach summary</h3>
                <p className="scouting-summary-text">{bundle.defense.assistantSummary}</p>
              </section>
            </div>
          )}
        </>
      )}
    </div>
  )
}
