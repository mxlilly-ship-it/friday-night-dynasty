import { useCallback, useEffect, useRef, useState } from 'react'
import './GamePlayPage.css'
import TeamLogo from './TeamLogo'

type GameState = {
  quarter: number
  time_remaining: number
  ball_position: number
  down: number
  yards_to_go: number
  score_home: number
  score_away: number
  possession: 'home' | 'away'
  home_team_name: string
  away_team_name: string
  user_team_name: string
  is_overtime?: boolean
  ot_period?: number
  ot_winner?: string | null
  pending_pat?: boolean
  team_stats?: Record<string, { total_yards?: number; rush_yards?: number; pass_yards?: number; touchdowns?: number; turnovers?: number; third_down?: string; fourth_down?: string; time_of_possession?: string; explosives?: number }>
}

/** Full field: 0 = home goal line, 100 = away goal line (matches engine ball_position). */
const FIELD_YARD_MARKERS: { leftPct: number; label: string }[] = [
  { leftPct: 0, label: '0' },
  { leftPct: 10, label: '10' },
  { leftPct: 20, label: '20' },
  { leftPct: 30, label: '30' },
  { leftPct: 40, label: '40' },
  { leftPct: 50, label: '50' },
  { leftPct: 60, label: '40' },
  { leftPct: 70, label: '30' },
  { leftPct: 80, label: '20' },
  { leftPct: 90, label: '10' },
  { leftPct: 100, label: '0' },
]

/** Five-yard ticks on the playing field only (excludes end zones). */
const FIELD_MINOR_YARD_PCTS = [15, 25, 35, 45, 55, 65, 75, 85]

/** Absolute field 0 = home goal, 100 = away goal — label must follow possession (e.g. away touchback at 75 is own 25, not opp 25). */
function possessionYardLineLabel(possession: 'home' | 'away', ballPosition: number): string {
  const b = Math.round(ballPosition)
  if (possession === 'home') {
    return b <= 50 ? `Own ${b}` : `Opp ${100 - b}`
  }
  return b >= 50 ? `Own ${100 - b}` : `Opp ${b}`
}

type PlayOption = { id: string; name: string; category: string; formation?: string }
type PlayOptions = {
  offense_team: string
  defense_team: string
  ai: { offense_play_id: string | null; defense_play_id: string | null }
  offense_plays: PlayOption[]
  defense_plays: PlayOption[]
}

type Props = {
  apiBase: string
  headers: Record<string, string>
  saveId: string
  saveState: any
  gameId: string
  homeTeam: string
  awayTeam: string
  userTeam: string
  /** Bumps logo URLs after upload (same as team home). */
  logoVersion?: number
  initialState: GameState
  /** When finishing a local-bundle game, pass `{ game }` (serialized engine game) so the client can call /sim/game/finish-*. */
  onContinue: (gameOver: boolean, finishPayload?: { game?: any }) => void | Promise<void>
  onError: (msg: string) => void
}

export default function GamePlayPage({
  apiBase,
  headers,
  saveId,
  saveState,
  gameId,
  homeTeam,
  awayTeam,
  userTeam,
  logoVersion = 0,
  initialState,
  onContinue,
  onError,
}: Props) {
  const [state, setState] = useState<GameState>(initialState)
  const [localGame, setLocalGame] = useState<any>(null)
  const [options, setOptions] = useState<PlayOptions | null>(null)
  const [selectedPlay, setSelectedPlay] = useState<PlayOption | null>(null)
  const [selectedCategory, setSelectedCategory] = useState<string>('')
  const [previousPlay, setPreviousPlay] = useState<string | null>(null)
  const [previousOpponentPlay, setPreviousOpponentPlay] = useState<string | null>(null)
  const [lastResult, setLastResult] = useState<string | null>(null)
  const [driveArrows, setDriveArrows] = useState<Array<{ from: number; to: number }>>([])
  const [loading, setLoading] = useState(false)
  const [simulating, setSimulating] = useState<string | null>(null)
  const [playFeed, setPlayFeed] = useState<string[]>([])
  const playFeedEndRef = useRef<HTMLDivElement>(null)

  const sameTeam = (a: string, b: string) => a.trim().toLowerCase() === b.trim().toLowerCase()
  const isUserOnOffense = state.possession === 'home' ? sameTeam(userTeam, homeTeam) : sameTeam(userTeam, awayTeam)
  const gameOver = !!state.ot_winner || (state.quarter > 4 && !state.is_overtime)
  const isLocalBundle = saveId === '__local__'

  const finishPayloadIfNeeded = (ended: boolean) =>
    isLocalBundle && ended ? { game: localGame } : undefined

  const fetchOptions = useCallback(async () => {
    try {
      const r = isLocalBundle
        ? await fetch(`${apiBase}/sim/game/options`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ state: saveState ?? {}, game: localGame ?? {} }),
          })
        : await fetch(`${apiBase}/games/${gameId}/options?save_id=${encodeURIComponent(saveId)}`, { headers })
      if (!r.ok) throw new Error('Failed to load play options')
      const data = await r.json()
      const opts = data.options as PlayOptions
      if (opts && state.down === 4 && !state.is_overtime) {
        const off = Array.isArray(opts.offense_plays) ? [...opts.offense_plays] : []
        const def = Array.isArray(opts.defense_plays) ? [...opts.defense_plays] : []
        if (!off.some((p) => p.id === 'PUNT')) {
          off.push({ id: 'PUNT', name: 'Punt', category: 'FOURTH_DOWN_SPECIAL', formation: '' })
        }
        if (!off.some((p) => p.id === 'FIELD_GOAL')) {
          off.push({ id: 'FIELD_GOAL', name: 'Field goal', category: 'FOURTH_DOWN_SPECIAL', formation: '' })
        }
        if (!def.some((p) => p.id === 'DEF_PUNT_RETURN')) {
          def.push({ id: 'DEF_PUNT_RETURN', name: 'Punt - return / safe', category: 'SPECIAL_TEAMS_DEFENSE', formation: '' })
        }
        if (!def.some((p) => p.id === 'DEF_PUNT_BLOCK')) {
          def.push({ id: 'DEF_PUNT_BLOCK', name: 'Punt - block', category: 'SPECIAL_TEAMS_DEFENSE', formation: '' })
        }
        if (!def.some((p) => p.id === 'DEF_FG_BLOCK')) {
          def.push({ id: 'DEF_FG_BLOCK', name: 'Field goal - block', category: 'SPECIAL_TEAMS_DEFENSE', formation: '' })
        }
        opts.offense_plays = off
        opts.defense_plays = def
      }
      setOptions(opts)
      if (opts) {
        const userOff = userTeam === opts.offense_team
        const plays = (userOff ? opts.offense_plays : opts.defense_plays) as PlayOption[]
        const catLabels = plays.map((p) => String(p.category || 'Other'))
        const cats = [...new Set(catLabels)].sort((a, b) => a.localeCompare(b))
        const fourthCat = 'FOURTH_DOWN_SPECIAL'
        const preferFourth =
          userOff && state.down === 4 && !state.is_overtime && cats.includes(fourthCat)
        const cat = preferFourth ? fourthCat : cats[0] ?? ''
        const inCat = plays.filter((p: PlayOption) => (p.category || 'Other') === cat)
        setSelectedCategory(cat)
        setSelectedPlay(inCat[0] || plays[0] || null)
      }
    } catch (e: unknown) {
      onError(e instanceof Error ? e.message : 'Failed to load options')
    }
  }, [apiBase, gameId, saveId, headers, userTeam, isLocalBundle, localGame, saveState, state.down, state.is_overtime])

  useEffect(() => {
    if (!isLocalBundle) return
    // For local bundle coach-play, the "gameId" is just a dummy; initialState is provided from /sim/game/start.
    // Store full serialized game object on first render when present.
    if ((initialState as any) && (initialState as any).__game && !localGame) {
      setLocalGame((initialState as any).__game)
    }
  }, [isLocalBundle, initialState, localGame])

  useEffect(() => {
    if (!gameOver) fetchOptions()
  }, [gameId, saveId, gameOver, state.possession, state.down, state.ball_position, state.pending_pat, fetchOptions])

  useEffect(() => {
    setPlayFeed([])
  }, [gameId])
  useEffect(() => {
    playFeedEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }, [playFeed])

  const formatTime = (sec: number) => {
    const m = Math.floor(sec / 60)
    const s = sec % 60
    return `${m}:${s.toString().padStart(2, '0')}`
  }

  const runPlay = async () => {
    if (!options || !selectedPlay || loading) return
    setLoading(true)
    try {
      let offensePlayId = isUserOnOffense ? selectedPlay.id : options.ai.offense_play_id
      let defensePlayId = isUserOnOffense ? options.ai.defense_play_id : selectedPlay.id
      // If user controls defense and picks a special-teams defense call, force matching offense call.
      // Otherwise backend treats DEF_PUNT_* / DEF_FG_BLOCK as invalid against normal offensive plays.
      if (!isUserOnOffense) {
        if (defensePlayId === 'DEF_PUNT_RETURN' || defensePlayId === 'DEF_PUNT_BLOCK') offensePlayId = 'PUNT'
        if (defensePlayId === 'DEF_PUNT_ALL_OUT_BLOCK') offensePlayId = 'PUNT'
        if (defensePlayId === 'DEF_FG_BLOCK') offensePlayId = 'FIELD_GOAL'
        if (defensePlayId === 'KICKOFF_RETURN_MIDDLE_WEDGE') offensePlayId = 'KICKOFF_DEEP'
        if (defensePlayId === 'KICKOFF_RETURN_FIELD_RETURN') offensePlayId = 'KICKOFF_DEEP'
        if (defensePlayId === 'KICKOFF_RETURN_REVERSE') offensePlayId = 'KICKOFF_DEEP'
      }
      if (!offensePlayId) throw new Error('Missing play selection')
      if (
        !defensePlayId &&
        offensePlayId !== 'PUNT' &&
        offensePlayId !== 'FIELD_GOAL' &&
        offensePlayId !== 'PAT_KICK' &&
        offensePlayId !== 'PAT_2PT'
      )
        throw new Error('Missing play selection')
      if (!defensePlayId) defensePlayId = options.defense_plays[0]?.id ?? ''

      const snapPos = state.ball_position
      const r = isLocalBundle
        ? await fetch(`${apiBase}/sim/game/play`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              state: saveState ?? {},
              game: localGame ?? {},
              offense_play_id: offensePlayId,
              defense_play_id: defensePlayId,
            }),
          })
        : await fetch(`${apiBase}/games/${gameId}/play?save_id=${encodeURIComponent(saveId)}`, {
            method: 'POST',
            headers: { ...headers, 'Content-Type': 'application/json' },
            body: JSON.stringify({ offense_play_id: offensePlayId, defense_play_id: defensePlayId }),
          })
      if (!r.ok) throw new Error('Play failed')
      const data = await r.json()

      const prevPossession = state.possession
      if (isLocalBundle && data.game) setLocalGame(data.game)
      setState(data.state)
      setPreviousPlay(isUserOnOffense ? selectedPlay.name : (options.offense_plays.find((p: PlayOption) => p.id === offensePlayId)?.name ?? '—'))
      setPreviousOpponentPlay(isUserOnOffense ? (options.defense_plays.find((p: PlayOption) => p.id === defensePlayId)?.name ?? '—') : selectedPlay.name)

      const res = data.result
      let resultText = `${res?.yards ?? 0} yards`
      if (res?.needs_pat) resultText = 'Touchdown! — Choose PAT (kick or 2-pt).'
      else if (res?.touchdown) resultText = 'Touchdown!'
      else if (res?.pat) {
        if (res?.pat_2pt) resultText = res?.pat_success ? 'Two-point good!' : 'Two-point no good.'
        else if (res?.pat_blocked) resultText = 'Extra point blocked!'
        else if (res?.pat_success) resultText = 'Extra point good!'
        else resultText = 'Extra point no good.'
      } else if (res?.kneel) resultText = res?.turnover ? 'Took a knee — turnover on downs.' : 'Took a knee — clock runs.'
      else if (res?.interception) resultText = 'Interception!'
      else if (res?.turnover) resultText = 'Turnover!'
      else if (res?.sack) resultText = `Sack! ${res.yards} yards`
      else if (res?.punt) resultText = 'Punt'
      else if (res?.field_goal) resultText = res?.field_goal_good ? 'Field Goal Good!' : 'Field Goal Missed'
      else if (res?.kickoff)
        resultText = res?.kickoff_td
          ? 'Kickoff return touchdown!'
          : res?.touchback
            ? 'Kickoff — touchback'
            : `Kickoff return (${res?.return_yards ?? 0} yds)`
      setLastResult(resultText)

      const nar = data.narrative
      if (typeof nar === 'string' && nar.trim()) {
        setPlayFeed((f) => [...f, nar.trim()])
      }

      const possessionChanged = prevPossession !== data.state.possession
      if (res?.touchdown || res?.turnover || possessionChanged) {
        setDriveArrows([])
      } else {
        setDriveArrows((prev) => [...prev, { from: snapPos, to: data.state.ball_position }])
      }
      await fetchOptions()
    } catch (e: unknown) {
      onError(e instanceof Error ? e.message : 'Play failed')
    } finally {
      setLoading(false)
    }
  }

  const simAction = async (action: 'sim-next' | 'sim-to-half' | 'sim-to-end') => {
    setSimulating(action)
    try {
      const r = isLocalBundle
        ? await fetch(`${apiBase}/sim/game/${action}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ state: saveState ?? {}, game: localGame ?? {} }),
          })
        : await fetch(`${apiBase}/games/${gameId}/${action}?save_id=${encodeURIComponent(saveId)}`, {
            method: 'POST',
            headers,
          })
      if (!r.ok) {
        const txt = await r.text()
        let msg = 'Simulation failed'
        try {
          const j = JSON.parse(txt) as { detail?: unknown }
          const d = j.detail
          if (typeof d === 'string') msg = d
          else if (Array.isArray(d))
            msg = d.map((x: { msg?: string }) => x?.msg || JSON.stringify(x)).join('; ')
          else if (txt.trim()) msg = txt
        } catch {
          if (txt.trim()) msg = txt
        }
        throw new Error(msg)
      }
      const data = await r.json()
      if (isLocalBundle && data.game) setLocalGame(data.game)
      setState(data.state)
      setDriveArrows([])
      const batch = data.narratives
      if (Array.isArray(batch) && batch.length > 0) {
        setPlayFeed((f) => [...f, ...batch.map((s: string) => String(s).trim()).filter(Boolean)])
      } else if (typeof data.narrative === 'string' && data.narrative.trim()) {
        setPlayFeed((f) => [...f, data.narrative.trim()])
      }
      if (!data.game_over) await fetchOptions()
    } catch (e: unknown) {
      onError(e instanceof Error ? e.message : 'Simulation failed')
    } finally {
      setSimulating(null)
    }
  }

  const plays = options ? (isUserOnOffense ? options.offense_plays : options.defense_plays) : []
  const byCategory = plays.reduce<Record<string, PlayOption[]>>((acc, p) => {
    const cat = p.category || 'Other'
    if (!acc[cat]) acc[cat] = []
    acc[cat].push(p)
    return acc
  }, {})
  const categories = Object.keys(byCategory).sort((a, b) => {
    const pri = (c: string) => {
      if (c.startsWith('AFTER_TOUCHDOWN')) return 0
      if (c === 'FOURTH_DOWN_SPECIAL') return 0.25
      if (c.includes('SPECIAL_TEAMS')) return 1
      return 9
    }
    const pa = pri(a)
    const pb = pri(b)
    if (pa !== pb) return pa - pb
    return a.localeCompare(b)
  })
  const playsInCategory = selectedCategory ? (byCategory[selectedCategory] || []) : []

  const hs = state.team_stats?.[homeTeam]
  const as = state.team_stats?.[awayTeam]

  return (
    <div className="gameplay-root">
      <header className="gameplay-header">
        <div className="gameplay-header-left gameplay-header-matchup">
          <div className={`gameplay-matchup-side ${userTeam === homeTeam ? 'gameplay-matchup-user' : ''}`}>
            <TeamLogo
              apiBase={apiBase}
              headers={headers}
              teamName={homeTeam}
              logoVersion={logoVersion}
              size={40}
            />
            <div className="gameplay-team-name">{homeTeam}</div>
          </div>
          <span className="gameplay-matchup-vs" aria-hidden>
            vs
          </span>
          <div className={`gameplay-matchup-side ${userTeam === awayTeam ? 'gameplay-matchup-user' : ''}`}>
            <TeamLogo
              apiBase={apiBase}
              headers={headers}
              teamName={awayTeam}
              logoVersion={logoVersion}
              size={40}
            />
            <div className="gameplay-team-name">{awayTeam}</div>
          </div>
        </div>
        <div className="gameplay-header-center">
          <span className="gameplay-meta">You: {userTeam}</span>
        </div>
        <div className="gameplay-header-right">
          <button
            type="button"
            className="gameplay-btn gameplay-btn-continue"
            onClick={() => onContinue(gameOver, finishPayloadIfNeeded(gameOver))}
          >
            CONTINUE
          </button>
        </div>
      </header>

      <div className="gameplay-scoreboard">
        <div className="gameplay-team-block gameplay-team-block-home">
          <div className="gameplay-team-identity">
            <TeamLogo
              apiBase={apiBase}
              headers={headers}
              teamName={homeTeam}
              logoVersion={logoVersion}
              size={48}
            />
            <div className="gameplay-team-label">{homeTeam}</div>
          </div>
          <div className="gameplay-score">{state.score_home}</div>
        </div>
        <div className="gameplay-clock-block">
          <div className="gameplay-time">{formatTime(state.time_remaining)}</div>
          <div className="gameplay-quarter">Q{state.quarter}{state.is_overtime ? ` OT${state.ot_period || 1}` : ''}</div>
          <div className="gameplay-down">
            {state.down} & {state.yards_to_go}
          </div>
          <div className="gameplay-yardline">
            Ball: {possessionYardLineLabel(state.possession, state.ball_position)}
          </div>
        </div>
        <div className="gameplay-team-block gameplay-team-block-away">
          <div className="gameplay-team-identity">
            <TeamLogo
              apiBase={apiBase}
              headers={headers}
              teamName={awayTeam}
              logoVersion={logoVersion}
              size={48}
            />
            <div className="gameplay-team-label">{awayTeam}</div>
          </div>
          <div className="gameplay-score">{state.score_away}</div>
        </div>
      </div>

      <div className="gameplay-main">
        <div className="gameplay-left-panel">
          <div className="gameplay-panel-title">Play Type: Category</div>
          <select
            className="gameplay-category-select"
            value={selectedCategory}
            onChange={(e) => {
              const cat = e.target.value
              setSelectedCategory(cat)
              const list = byCategory[cat] || []
              setSelectedPlay(list[0] || null)
            }}
            disabled={gameOver || categories.length === 0}
          >
            {categories.map((cat) => (
              <option key={cat} value={cat}>
                {cat === 'FOURTH_DOWN_SPECIAL' ? '4th down — punt / field goal' : cat.replace(/_/g, ' ')}
              </option>
            ))}
          </select>
          <div className="gameplay-playbook">
            {playsInCategory.map((p) => (
              <button
                key={p.id}
                type="button"
                className={`gameplay-play-btn ${selectedPlay?.id === p.id ? 'selected' : ''}`}
                onClick={() => setSelectedPlay(p)}
                disabled={gameOver}
              >
                <span className="gameplay-play-name">{p.name}</span>
                {p.formation && <span className="gameplay-play-formation">({p.formation})</span>}
              </button>
            ))}
          </div>
          <div className="gameplay-selected-label">Play Selected</div>
          <div className="gameplay-selected-box">
            {selectedPlay ? (
              <>
                {selectedPlay.name}
                {selectedPlay.formation && <span className="gameplay-play-formation"> ({selectedPlay.formation})</span>}
              </>
            ) : (
              '—'
            )}
          </div>
          <div className="gameplay-actions">
            <button
              type="button"
              className="gameplay-action-btn gameplay-run"
              onClick={runPlay}
              disabled={!selectedPlay || loading || gameOver}
            >
              {loading ? '…' : '▶'} Run Play
            </button>
            <button
              type="button"
              className="gameplay-action-btn gameplay-sim"
              onClick={() => simAction('sim-next')}
              disabled={!!simulating || gameOver}
            >
              {simulating === 'sim-next' ? '…' : '▶'} Sim to Next Play
            </button>
            <button
              type="button"
              className="gameplay-action-btn gameplay-sim"
              onClick={() => simAction('sim-to-half')}
              disabled={!!simulating || gameOver}
            >
              {simulating === 'sim-to-half' ? '…' : '▶'} Sim to Half
            </button>
            <button
              type="button"
              className="gameplay-action-btn gameplay-sim"
              onClick={() => simAction('sim-to-end')}
              disabled={!!simulating || gameOver}
            >
              {simulating === 'sim-to-end' ? '…' : '▶'} Sim to End
            </button>
          </div>
        </div>

        <div className="gameplay-center-stack">
          <div className="gameplay-field-wrap">
            <div className="gameplay-field" role="img" aria-label="Football field, ball position by yard line">
              <div className="gameplay-field-layer gameplay-field-turf" aria-hidden />
              <div className="gameplay-field-layer gameplay-field-endzone gameplay-field-endzone--home" aria-hidden>
                <span className="gameplay-field-endzone-text">END ZONE</span>
              </div>
              <div className="gameplay-field-layer gameplay-field-endzone gameplay-field-endzone--away" aria-hidden>
                <span className="gameplay-field-endzone-text">END ZONE</span>
              </div>
              <div className="gameplay-field-layer gameplay-field-yardlines-major" aria-hidden />
              <div className="gameplay-field-layer gameplay-field-goal-lines" aria-hidden />
              {FIELD_MINOR_YARD_PCTS.map((pct) => (
                <div key={pct} className="gameplay-yard-tick-minor" style={{ left: `${pct}%` }} aria-hidden />
              ))}
              <div className="gameplay-field-layer gameplay-field-hashes gameplay-field-hashes--upper" aria-hidden />
              <div className="gameplay-field-layer gameplay-field-hashes gameplay-field-hashes--lower" aria-hidden />
              <div className="gameplay-field-content">
                {FIELD_YARD_MARKERS.map((m) => (
                  <div key={m.leftPct} className="gameplay-yardline-marker" style={{ left: `${m.leftPct}%` }}>
                    <span className="gameplay-yardline-num">{m.label}</span>
                  </div>
                ))}
                {driveArrows.map((arr, i) => {
                  const min = Math.min(arr.from, arr.to)
                  const width = Math.abs(arr.to - arr.from)
                  return (
                    <div
                      key={i}
                      className="gameplay-drive-arrow"
                      style={{
                        left: `${min}%`,
                        width: `${width}%`,
                        transform: arr.to >= arr.from ? 'translateY(-50%)' : 'translateY(-50%) scaleX(-1)',
                      }}
                    />
                  )
                })}
                <div className="gameplay-ball" style={{ left: `${state.ball_position}%` }} title="Ball" />
              </div>
            </div>
          </div>

          <div className="gameplay-stats gameplay-stats-under-field gameplay-stats-vertical">
            <div className="gameplay-stats-vertical-head">
              <div className="gameplay-stats-team-col">
                <span className="gameplay-stats-team-abbr" title={homeTeam}>
                  {homeTeam.length > 12 ? `${homeTeam.slice(0, 10)}…` : homeTeam}
                </span>
              </div>
              <div className="gameplay-stats-team-col gameplay-stats-team-col--away">
                <span className="gameplay-stats-team-abbr" title={awayTeam}>
                  {awayTeam.length > 12 ? `${awayTeam.slice(0, 10)}…` : awayTeam}
                </span>
              </div>
            </div>
            <ul className="gameplay-stats-vertical-list">
              <li className="gameplay-stat-vrow">
                <span className="gameplay-stat-vlabel">Points</span>
                <span className="gameplay-stat-vval">{state.score_home}</span>
                <span className="gameplay-stat-vval gameplay-stat-vval--away">{state.score_away}</span>
              </li>
              <li className="gameplay-stat-vrow">
                <span className="gameplay-stat-vlabel">Total yds</span>
                <span className="gameplay-stat-vval">{hs?.total_yards ?? 0}</span>
                <span className="gameplay-stat-vval gameplay-stat-vval--away">{as?.total_yards ?? 0}</span>
              </li>
              <li className="gameplay-stat-vrow">
                <span className="gameplay-stat-vlabel">Rushing</span>
                <span className="gameplay-stat-vval">{hs?.rush_yards ?? 0}</span>
                <span className="gameplay-stat-vval gameplay-stat-vval--away">{as?.rush_yards ?? 0}</span>
              </li>
              <li className="gameplay-stat-vrow">
                <span className="gameplay-stat-vlabel">Passing</span>
                <span className="gameplay-stat-vval">{hs?.pass_yards ?? 0}</span>
                <span className="gameplay-stat-vval gameplay-stat-vval--away">{as?.pass_yards ?? 0}</span>
              </li>
              <li className="gameplay-stat-vrow">
                <span className="gameplay-stat-vlabel">Turnovers</span>
                <span className="gameplay-stat-vval">{hs?.turnovers ?? 0}</span>
                <span className="gameplay-stat-vval gameplay-stat-vval--away">{as?.turnovers ?? 0}</span>
              </li>
              <li className="gameplay-stat-vrow">
                <span className="gameplay-stat-vlabel">T.O.P.</span>
                <span className="gameplay-stat-vval">{hs?.time_of_possession ?? '0:00'}</span>
                <span className="gameplay-stat-vval gameplay-stat-vval--away">{as?.time_of_possession ?? '0:00'}</span>
              </li>
              <li className="gameplay-stat-vrow">
                <span className="gameplay-stat-vlabel">Explosives</span>
                <span className="gameplay-stat-vval">{hs?.explosives ?? 0}</span>
                <span className="gameplay-stat-vval gameplay-stat-vval--away">{as?.explosives ?? 0}</span>
              </li>
              <li className="gameplay-stat-vrow">
                <span className="gameplay-stat-vlabel">3rd down</span>
                <span className="gameplay-stat-vval">{hs?.third_down ?? '0/0'}</span>
                <span className="gameplay-stat-vval gameplay-stat-vval--away">{as?.third_down ?? '0/0'}</span>
              </li>
              <li className="gameplay-stat-vrow">
                <span className="gameplay-stat-vlabel">4th down</span>
                <span className="gameplay-stat-vval">{hs?.fourth_down ?? '0/0'}</span>
                <span className="gameplay-stat-vval gameplay-stat-vval--away">{as?.fourth_down ?? '0/0'}</span>
              </li>
            </ul>
          </div>
        </div>

        <div className="gameplay-right-panel">
          <div className="gameplay-panel-title">Previous Play</div>
          <div className="gameplay-history-box">{previousPlay ?? '—'}</div>
          <div className="gameplay-panel-title">Previous Opponent Play</div>
          <div className="gameplay-history-box">{previousOpponentPlay ?? '—'}</div>
          <div className="gameplay-panel-title">Play Result</div>
          <div className="gameplay-result-box">{lastResult ?? '—'}</div>
          <div className="gameplay-panel-title">Play-by-play</div>
          <div className="gameplay-play-feed" role="log" aria-live="polite">
            {playFeed.length === 0 ? (
              <div className="gameplay-play-feed-empty">Play calls will show here with player names.</div>
            ) : (
              playFeed.map((line, i) => (
                <div key={`${i}-${line.slice(0, 24)}`} className="gameplay-play-feed-line">
                  {line}
                </div>
              ))
            )}
            <div ref={playFeedEndRef} />
          </div>
        </div>
      </div>

      {gameOver && (
        <div className="gameplay-overlay">
          <div className="gameplay-overlay-inner">
            <h2>Game Over</h2>
            <p>
              {homeTeam} {state.score_home} – {awayTeam} {state.score_away}
              {state.ot_winner ? ' (OT)' : ''}
            </p>
            <button
              type="button"
              className="gameplay-btn gameplay-btn-continue"
              onClick={() => onContinue(true, finishPayloadIfNeeded(true))}
            >
              Continue
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
