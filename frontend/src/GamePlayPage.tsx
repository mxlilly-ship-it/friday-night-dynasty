import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import './GamePlayPage.css'
import './GameplayCallsheet.css'
import TeamLogo from './TeamLogo'
import {
  type CallsheetBucket,
  type CallsheetPlayRow,
  type CallsheetSide,
  CALLSHEET_BUCKET_ORDER,
  buildDefenseCallsheet,
  buildOffenseCallsheet,
  buildSpecialCallsheet,
  callsheetHeaderClass,
  callsheetHeaderTitle,
  createEmptyCallsheet,
} from './gameplayCallsheet'

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
  /** Mercy rule: 35+ spread in regulation — incomplete passes still burn clock; see engine. */
  running_clock?: boolean
  team_stats?: Record<string, { total_yards?: number; rush_yards?: number; pass_yards?: number; touchdowns?: number; turnovers?: number; third_down?: string; fourth_down?: string; time_of_possession?: string; explosives?: number }>
}

/** Full field: 0 = home goal line, 100 = away goal line (absolute). */
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

/**
 * Engine stores ball_position as yards from the current offense's own goal (0–100 toward the opponent).
 * Map to absolute field percent for the graphic: 0 = home goal, 100 = away goal.
 */
function absoluteFieldPct(possession: 'home' | 'away', ballPosition: number): number {
  const b = Math.max(0, Math.min(100, ballPosition))
  return possession === 'home' ? b : 100 - b
}

/** Label uses offense-relative ball (same as engine). */
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
  /** Call sheet column key for "PLAY TYPE" display (matches game_interface playType). */
  const [callsheetBucket, setCallsheetBucket] = useState<string>('')
  const [callsheetSide, setCallsheetSide] = useState<CallsheetSide>('offense')
  const [previousPlay, setPreviousPlay] = useState<string | null>(null)
  const [previousOpponentPlay, setPreviousOpponentPlay] = useState<string | null>(null)
  const [lastResult, setLastResult] = useState<string | null>(null)
  const [driveArrows, setDriveArrows] = useState<Array<{ from: number; to: number }>>([])
  const [loading, setLoading] = useState(false)
  const [simulating, setSimulating] = useState<string | null>(null)
  const [playFeed, setPlayFeed] = useState<string[]>([])
  const commentaryStripRef = useRef<HTMLDivElement>(null)

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
        const fourthCat = 'FOURTH_DOWN_SPECIAL'
        const hasFourth = plays.some((p) => (p.category || '') === fourthCat)
        const preferFourth = userOff && state.down === 4 && !state.is_overtime && hasFourth
        const pick =
          preferFourth ? plays.find((p) => (p.category || '') === fourthCat) : plays[0]
        setSelectedPlay(pick || plays[0] || null)
        setCallsheetBucket('')
        setCallsheetSide(userOff ? 'offense' : 'defense')
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
    setCallsheetSide(isUserOnOffense ? 'offense' : 'defense')
  }, [isUserOnOffense])

  useEffect(() => {
    setPlayFeed([])
  }, [gameId])
  useEffect(() => {
    const el = commentaryStripRef.current
    if (el && playFeed.length > 0) {
      el.scrollTo({ left: el.scrollWidth, behavior: 'smooth' })
    }
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

      const fromAbs = absoluteFieldPct(state.possession, state.ball_position)
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
      const toAbs = absoluteFieldPct(data.state.possession, data.state.ball_position)
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
        setDriveArrows((prev) => [...prev, { from: fromAbs, to: toAbs }])
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

  const gridPlays = useMemo(() => {
    if (!options) return createEmptyCallsheet()
    if (callsheetSide === 'offense') {
      return buildOffenseCallsheet(
        options.offense_plays,
        isUserOnOffense,
        state.ball_position,
        state.down,
        state.yards_to_go,
      )
    }
    if (callsheetSide === 'defense') {
      return buildDefenseCallsheet(
        options.defense_plays,
        isUserOnOffense,
        state.ball_position,
        state.down,
        state.yards_to_go,
      )
    }
    return buildSpecialCallsheet(
      options.offense_plays,
      options.defense_plays,
      isUserOnOffense,
      state.ball_position,
      state.down,
      state.yards_to_go,
    )
  }, [
    options,
    callsheetSide,
    isUserOnOffense,
    state.ball_position,
    state.down,
    state.yards_to_go,
  ])

  const tagClass: Record<string, string> = {
    base: 'tag-base',
    'red-zone': 'tag-red-zone',
    third: 'tag-third',
    trick: 'tag-trick',
  }
  const tagLabel: Record<string, string> = {
    base: 'BASE',
    'red-zone': 'RZ',
    third: '3RD',
    trick: 'TRK',
  }

  const selectCallsheetPlay = (row: CallsheetPlayRow, bucket: CallsheetBucket) => {
    if (!options || gameOver) return
    const userPool = isUserOnOffense ? options.offense_plays : options.defense_plays
    const inUserList = userPool.some((p) => p.id === row.id)
    const canSelect =
      (callsheetSide === 'offense' && isUserOnOffense) ||
      (callsheetSide === 'defense' && !isUserOnOffense) ||
      (callsheetSide === 'special' && inUserList)
    if (!canSelect) return
    const full = [...options.offense_plays, ...options.defense_plays].find((p) => p.id === row.id)
    if (!full) return
    setSelectedPlay(full)
    setCallsheetBucket(bucket.toUpperCase())
  }

  const hs = state.team_stats?.[homeTeam]
  const as = state.team_stats?.[awayTeam]

  const playTypeDisplay =
    callsheetBucket || (selectedPlay?.category ? String(selectedPlay.category).replace(/_/g, ' ') : '—')

  type InlineStat = { label: string; value: string | number; narrow?: boolean }

  const buildInlineStats = (s: typeof hs, score: number): InlineStat[] => [
    { label: 'Pts', value: score },
    { label: 'Yds', value: s?.total_yards ?? 0 },
    { label: 'Rush', value: s?.rush_yards ?? 0 },
    { label: 'Pass', value: s?.pass_yards ?? 0 },
    { label: 'TO', value: s?.turnovers ?? 0 },
    { label: 'TOP', value: s?.time_of_possession ?? '0:00', narrow: true },
    { label: 'Xpl', value: s?.explosives ?? 0 },
    { label: '3rd', value: s?.third_down ?? '0/0', narrow: true },
    { label: '4th', value: s?.fourth_down ?? '0/0', narrow: true },
  ]

  const renderStatColumn = (items: InlineStat[], side: 'home' | 'away') => (
    <ul className={`gameplay-inline-stats-col gameplay-inline-stats-col--${side}`}>
      {items.map((row) => (
        <li key={row.label}>
          <span className="gameplay-inline-stat-lbl">{row.label}</span>
          <span
            className={`gameplay-inline-stat-val${row.narrow ? ' gameplay-inline-stat-val--narrow' : ''}`}
          >
            {row.value}
          </span>
        </li>
      ))}
    </ul>
  )

  const renderTeamStatGrid = (s: typeof hs, score: number, side: 'home' | 'away') => {
    const all = buildInlineStats(s, score)
    const split = Math.ceil(all.length / 2)
    return (
      <div className="gameplay-team-stats-cols" aria-label={`${side === 'home' ? homeTeam : awayTeam} stats`}>
        {renderStatColumn(all.slice(0, split), side)}
        {renderStatColumn(all.slice(split), side)}
      </div>
    )
  }

  return (
    <div className="gameplay-root">
      <header className="gameplay-header">
        <div className="gameplay-header-left gameplay-header-matchup">
          <div className={`gameplay-matchup-side ${userTeam === homeTeam ? 'gameplay-matchup-user' : ''}`}>
            <div className="gameplay-team-name">{homeTeam}</div>
          </div>
          <span className="gameplay-matchup-vs" aria-hidden>
            vs
          </span>
          <div className={`gameplay-matchup-side ${userTeam === awayTeam ? 'gameplay-matchup-user' : ''}`}>
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
          <div className="gameplay-team-block-inner">
            <div className="gameplay-team-score-stack">
              <div className="gameplay-team-label gameplay-team-label--board" title={homeTeam}>
                {homeTeam.length > 18 ? `${homeTeam.slice(0, 16)}…` : homeTeam}
              </div>
              <TeamLogo
                apiBase={apiBase}
                headers={headers}
                teamName={homeTeam}
                logoVersion={logoVersion}
                size={52}
              />
              <div className="gameplay-score">{state.score_home}</div>
            </div>
            {renderTeamStatGrid(hs, state.score_home, 'home')}
          </div>
        </div>
        <div className="gameplay-clock-block">
          <div className="gameplay-time">{formatTime(state.time_remaining)}</div>
          <div className="gameplay-quarter">Q{state.quarter}{state.is_overtime ? ` OT${state.ot_period || 1}` : ''}</div>
          {state.running_clock && !state.is_overtime ? (
            <div
              className="gameplay-running-clock"
              title="35+ point margin: clock keeps moving on incomplete passes. In Q4, period time is capped at 2:00."
            >
              Running clock · 35+
            </div>
          ) : null}
          <div className="gameplay-down">
            {state.down} & {state.yards_to_go}
          </div>
          <div className="gameplay-yardline">
            Ball: {possessionYardLineLabel(state.possession, state.ball_position)}
          </div>
        </div>
        <div className="gameplay-team-block gameplay-team-block-away">
          <div className="gameplay-team-block-inner gameplay-team-block-inner--away">
            {renderTeamStatGrid(as, state.score_away, 'away')}
            <div className="gameplay-team-score-stack">
              <div className="gameplay-team-label gameplay-team-label--board" title={awayTeam}>
                {awayTeam.length > 18 ? `${awayTeam.slice(0, 16)}…` : awayTeam}
              </div>
              <TeamLogo
                apiBase={apiBase}
                headers={headers}
                teamName={awayTeam}
                logoVersion={logoVersion}
                size={52}
              />
              <div className="gameplay-score">{state.score_away}</div>
            </div>
          </div>
        </div>
      </div>

      <div className="gameplay-body">
        <div className="gameplay-main">
          <div className="gameplay-center-stack">
          <div className="gameplay-center-upper">
          <div
            ref={commentaryStripRef}
            className="gameplay-commentary-strip"
            role="log"
            aria-live="polite"
            aria-label="Play-by-play"
          >
            {playFeed.length === 0 ? (
              <span className="gameplay-commentary-strip-empty">Play-by-play will appear here after each snap.</span>
            ) : (
              playFeed.map((line, i) => (
                <span key={`${i}-${line.slice(0, 20)}`} className="gameplay-commentary-strip-item">
                  {line}
                </span>
              ))
            )}
          </div>

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
                <div
                  className="gameplay-ball"
                  style={{ left: `${absoluteFieldPct(state.possession, state.ball_position)}%` }}
                  title="Ball"
                />
              </div>
            </div>
          </div>
          </div>

          <div className="gameplay-play-panel">
            <div className="gameplay-playbar-strip">
              <label htmlFor="gameplay-selected-play-display">Play selected</label>
              <div id="gameplay-selected-play-display" className="gameplay-play-display">
                {selectedPlay
                  ? `${selectedPlay.name}${selectedPlay.formation ? ` (${selectedPlay.formation})` : ''}`
                  : '—'}
              </div>
              <div className="gameplay-playbar-actions">
                <button
                  type="button"
                  className="gameplay-btn-action"
                  onClick={() => void runPlay()}
                  disabled={!selectedPlay || loading || gameOver}
                >
                  RUN PLAY
                </button>
                <button
                  type="button"
                  className="gameplay-btn-action gameplay-btn-action--alt"
                  onClick={() => void simAction('sim-next')}
                  disabled={!!simulating || gameOver}
                >
                  SIM TO NEXT PLAY
                </button>
              </div>
            </div>

            <div className="gameplay-play-meta-row" aria-label="Last play summary">
              <span className="gameplay-meta-chip">
                <span className="gameplay-meta-chip-lbl">Prev</span>
                <span className="gameplay-meta-chip-val">{previousPlay ?? '—'}</span>
              </span>
              <span className="gameplay-meta-chip">
                <span className="gameplay-meta-chip-lbl">Opp</span>
                <span className="gameplay-meta-chip-val">{previousOpponentPlay ?? '—'}</span>
              </span>
              <span className="gameplay-meta-chip">
                <span className="gameplay-meta-chip-lbl">Type</span>
                <span className="gameplay-meta-chip-val">{playTypeDisplay}</span>
              </span>
              <span className="gameplay-meta-chip gameplay-meta-chip--result">
                <span className="gameplay-meta-chip-lbl">Result</span>
                <span className="gameplay-meta-chip-val">{lastResult ?? '—'}</span>
              </span>
            </div>
          </div>
        </div>

        <aside className="gameplay-right-rail" aria-label="Simulation shortcuts">
          <div className="gameplay-sim-row gameplay-sim-row--stack">
            <button
              type="button"
              className="gameplay-sim-row-btn"
              onClick={() => void simAction('sim-to-half')}
              disabled={!!simulating || gameOver}
            >
              {simulating === 'sim-to-half' ? '…' : 'Sim to Half'}
            </button>
            <button
              type="button"
              className="gameplay-sim-row-btn"
              onClick={() => void simAction('sim-to-end')}
              disabled={!!simulating || gameOver}
            >
              {simulating === 'sim-to-end' ? '…' : 'Sim to End'}
            </button>
          </div>
        </aside>
      </div>

        <div className="callsheet-section">
        <div className="callsheet-header">
          <h2>📋 Call Sheet</h2>
          <button
            type="button"
            className={`cs-tab ${callsheetSide === 'offense' ? 'active' : ''}`}
            onClick={() => setCallsheetSide('offense')}
          >
            OFFENSE
          </button>
          <button
            type="button"
            className={`cs-tab ${callsheetSide === 'defense' ? 'active' : ''}`}
            onClick={() => setCallsheetSide('defense')}
          >
            DEFENSE
          </button>
          <button
            type="button"
            className={`cs-tab ${callsheetSide === 'special' ? 'active' : ''}`}
            onClick={() => setCallsheetSide('special')}
          >
            SPECIAL TEAMS
          </button>
        </div>

        <div className="callsheet-grid">
          {CALLSHEET_BUCKET_ORDER.map((bucket) => (
            <div key={bucket} className="cs-category">
              <div className={`cs-cat-header ${callsheetHeaderClass(bucket)}`}>
                {callsheetHeaderTitle(bucket, callsheetSide)}
              </div>
              <div className="cs-plays">
                {(gridPlays[bucket] ?? []).map((row) => {
                  const userPool = options
                    ? isUserOnOffense
                      ? options.offense_plays
                      : options.defense_plays
                    : []
                  const inUserList = userPool.some((p) => p.id === row.id)
                  const canSelect =
                    (callsheetSide === 'offense' && isUserOnOffense) ||
                    (callsheetSide === 'defense' && !isUserOnOffense) ||
                    (callsheetSide === 'special' && inUserList)
                  const disabled = gameOver || !options || !canSelect
                  const tc = tagClass[row.tag] || 'tag-base'
                  const tl = tagLabel[row.tag] || 'BASE'
                  return (
                    <div
                      key={row.id}
                      role="button"
                      tabIndex={0}
                      className={`cs-play ${selectedPlay?.id === row.id ? 'selected' : ''} ${disabled ? 'cs-play--disabled' : ''}`}
                      onClick={() => !disabled && selectCallsheetPlay(row, bucket)}
                      onKeyDown={(e) => {
                        if (disabled) return
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault()
                          selectCallsheetPlay(row, bucket)
                        }
                      }}
                    >
                      <div className="play-dot" />
                      <span className="cs-play-text">
                        <span className="cs-play-title">{row.name}</span>
                        {row.formation ? <span className="cs-play-formation">{row.formation}</span> : null}
                      </span>
                      <span className={`play-tag ${tc}`}>{tl}</span>
                    </div>
                  )
                })}
              </div>
            </div>
          ))}
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
