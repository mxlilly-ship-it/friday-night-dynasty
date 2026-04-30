import { useCallback, useEffect, useMemo, useState } from 'react'
import './TeamHomePage.css'
import {
  PLAYER_ATTRIBUTE_COLUMNS_SCROLL,
  formatPlayerAttributeCell,
  formatPlayerMeasureLine,
  rosterDepthTableGridTemplateColumns,
} from './playerAttributes'
import { PlayerProfileName } from './PlayerProfileContext'

const OFFENSE_POSITIONS = ['QB', 'RB', 'WR', 'OL', 'TE'] as const
const DEFENSE_POSITIONS = ['DE', 'DT', 'LB', 'CB', 'S'] as const
const ALL_POSITIONS = [...OFFENSE_POSITIONS, ...DEFENSE_POSITIONS] as const

const POSITION_DEPTH: Record<string, number> = {
  QB: 2, RB: 4, WR: 6, OL: 8, TE: 2,
  DE: 4, DT: 3, LB: 5, CB: 4, S: 3,
}

function computeOffenseRating(p: any, pos: string) {
  const get = (k: string) => Number(p?.[k] ?? 0)
  if (pos === 'QB') return (get('throw_power') + get('throw_accuracy') + get('decisions') + get('football_iq')) / 4
  if (pos === 'RB') return (get('speed') + get('break_tackle') + get('vision') + get('ball_security') + get('catching')) / 5
  if (pos === 'WR' || pos === 'TE') return (get('catching') + get('route_running') + get('speed') + get('agility')) / 4
  if (pos === 'OL') return (get('run_blocking') + get('pass_blocking') + get('strength')) / 3
  return 0
}

function computeDefenseRating(p: any, pos: string) {
  const get = (k: string) => Number(p?.[k] ?? 0)
  if (pos === 'DE' || pos === 'DT') return (get('pass_rush') + get('run_defense') + get('block_shedding') + get('strength')) / 4
  if (pos === 'LB') return (get('tackling') + get('pursuit') + get('coverage') + get('run_defense')) / 4
  if (pos === 'CB' || pos === 'S') return (get('coverage') + get('speed') + get('agility') + get('tackling')) / 4
  return 0
}

function getPlayerSidePosition(p: any, side: 'offense' | 'defense') {
  const allowed = (side === 'offense' ? OFFENSE_POSITIONS : DEFENSE_POSITIONS) as readonly string[]
  const primary = String(p?.position ?? '')
  const secondary = String(p?.secondary_position ?? '')
  if (allowed.includes(primary)) return primary
  if (allowed.includes(secondary)) return secondary
  return '—'
}

function getBestSideRating(p: any, side: 'offense' | 'defense') {
  const allowed = (side === 'offense' ? OFFENSE_POSITIONS : DEFENSE_POSITIONS) as readonly string[]
  const rate = side === 'offense' ? computeOffenseRating : computeDefenseRating
  const candidates = [String(p?.position ?? ''), String(p?.secondary_position ?? '')].filter((pos) =>
    allowed.includes(pos),
  )
  if (candidates.length === 0) return 0
  let best = 0
  for (const pos of candidates) best = Math.max(best, rate(p, pos))
  return Math.round(best)
}

/** Simple roster OVR (aligned with Team Home roster view). */
function computePlayerOverall(p: any) {
  const keys = [
    'speed',
    'agility',
    'acceleration',
    'strength',
    'football_iq',
    'coachability',
    'throw_accuracy',
    'catching',
    'run_blocking',
    'pass_blocking',
    'tackling',
    'coverage',
  ]
  const vals = keys.map((k) => Number(p?.[k] ?? 50))
  return Math.round(vals.reduce((a, b) => a + b, 0) / vals.length)
}

function formatPlayerYear(year: any) {
  if (year == null) return '—'
  const n = Number(year)
  if (Number.isNaN(n)) return String(year)
  if (n === 9 || n === 1) return 'FR'
  if (n === 10 || n === 2) return 'SO'
  if (n === 11 || n === 3) return 'JR'
  if (n === 12 || n === 4) return 'SR'
  return String(year)
}

type Props = {
  saveState: any
  userTeam: string
  apiBase?: string
  headers?: Record<string, string>
  isPreseason?: boolean
  onSave: (depthChart: Record<string, string[]>) => Promise<void>
  onBack?: () => void
}

function findTeam(state: any, teamName: string) {
  return (state?.teams ?? []).find((t: any) => t?.name === teamName) ?? null
}

export default function DepthChartPage({
  saveState,
  userTeam,
  isPreseason = false,
  onSave,
  onBack,
}: Props) {
  const userRoster = useMemo(() => findTeam(saveState, userTeam)?.roster ?? [], [saveState, userTeam])
  const savedOrder = useMemo(
    () => findTeam(saveState, userTeam)?.depth_chart_order ?? {},
    [saveState, userTeam],
  )

  const [selectedPos, setSelectedPos] = useState<string>('QB')
  const [localOrder, setLocalOrder] = useState<Record<string, string[]>>({})
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    const init: Record<string, string[]> = {}
    for (const pos of ALL_POSITIONS) {
      const slots = POSITION_DEPTH[pos] ?? 4
      const pool = getCandidatesForPosition(userRoster, pos)
      const saved = savedOrder[pos]
      if (saved && Array.isArray(saved)) {
        init[pos] = saved.filter((n) => typeof n === 'string').slice(0, slots)
      } else {
        init[pos] = pool.slice(0, slots).map((p: any) => p?.name ?? '—')
      }
      while (init[pos].length < slots) init[pos].push('—')
    }
    setLocalOrder(init)
  }, [userRoster, savedOrder])

  const setLocalOrderForPos = useCallback((pos: string, names: string[]) => {
    setLocalOrder((prev) => ({ ...prev, [pos]: [...names] }))
  }, [])

  const pool = useMemo(
    () => getCandidatesForPosition(userRoster, selectedPos),
    [userRoster, selectedPos],
  )

  const slots = POSITION_DEPTH[selectedPos] ?? 4
  const currentOrder = localOrder[selectedPos] ?? []

  const offensiveStarters = useMemo(
    () => buildStartersFromOrder(localOrder, userRoster, 'offense'),
    [localOrder, userRoster],
  )
  const defensiveStarters = useMemo(
    () => buildStartersFromOrder(localOrder, userRoster, 'defense'),
    [localOrder, userRoster],
  )

  const handleSlotChange = useCallback(
    (slotIndex: number, playerName: string) => {
      const next = [...currentOrder]
      while (next.length <= slotIndex) next.push('—')
      const prevName = next[slotIndex]
      next[slotIndex] = playerName === '' ? '—' : playerName
      if (prevName && prevName !== '—') {
        const idx = next.findIndex((n, i) => i !== slotIndex && n === playerName)
        if (idx >= 0) next[idx] = prevName
      }
      setLocalOrderForPos(selectedPos, next)
    },
    [currentOrder, selectedPos, setLocalOrderForPos],
  )

  const handleSave = useCallback(async () => {
    setSaving(true)
    try {
      const toSave: Record<string, string[]> = {}
      for (const pos of ALL_POSITIONS) {
        const arr = (localOrder[pos] ?? []).filter((n) => n && n !== '—')
        if (arr.length) toSave[pos] = arr
      }
      await onSave(toSave)
    } finally {
      setSaving(false)
    }
  }, [localOrder, onSave])

  const handleAutoDepthByOverall = useCallback(() => {
    setLocalOrder(buildAutoDepthChartOrder(userRoster))
  }, [userRoster])

  const depthCandidateGridCols = useMemo(
    () => rosterDepthTableGridTemplateColumns(PLAYER_ATTRIBUTE_COLUMNS_SCROLL.length),
    [],
  )

  return (
    <div className="teamhome-depth-shell">
      <div className="teamhome-depth-top">
        <div className="teamhome-depth-col">
          <div className="teamhome-depth-title">
            Position:{' '}
            <select
              className="teamhome-select teamhome-select-inline"
              value={selectedPos}
              onChange={(e) => setSelectedPos(e.target.value)}
            >
              {ALL_POSITIONS.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </div>
          <div className="teamhome-depth-stack">
            {Array.from({ length: slots }, (_, i) => (
              <div key={i} className="teamhome-depth-item depth-slot-row">
                <span>{i + 1}.</span>
                <select
                  className="teamhome-select-inline depth-slot-select"
                  value={currentOrder[i] ?? '—'}
                  onChange={(e) => handleSlotChange(i, e.target.value)}
                >
                  <option value="—">—</option>
                  {pool.map((p: any) => (
                    <option key={p?.name ?? i} value={p?.name ?? '—'}>
                      {p?.name ?? '—'}
                    </option>
                  ))}
                </select>
              </div>
            ))}
          </div>
        </div>

        <div className="teamhome-depth-col">
          <div className="teamhome-depth-title">Offensive starters</div>
          <div className="teamhome-depth-stack">
            {offensiveStarters.map((s, i) => (
              <div key={`${s.label}-${i}`} className="teamhome-depth-item">
                {s.label}:{' '}
                <PlayerProfileName teamName={userTeam} playerName={s.name} as="span" />
                {s.name !== '—' ? (
                  <span className="teamhome-depth-subline">
                    {s.measure ? `${s.measure} · ` : ''}
                    OFF {s.offPosition} ({s.offRating}) | DEF {s.defPosition} ({s.defRating})
                  </span>
                ) : null}
              </div>
            ))}
          </div>
        </div>

        <div className="teamhome-depth-col">
          <div className="teamhome-depth-title">Defensive starters</div>
          <div className="teamhome-depth-stack">
            {defensiveStarters.map((s, i) => (
              <div key={`${s.label}-${i}`} className="teamhome-depth-item">
                {s.label}:{' '}
                <PlayerProfileName teamName={userTeam} playerName={s.name} as="span" />
                {s.name !== '—' ? (
                  <span className="teamhome-depth-subline">
                    {s.measure ? `${s.measure} · ` : ''}
                    OFF {s.offPosition} ({s.offRating}) | DEF {s.defPosition} ({s.defRating})
                  </span>
                ) : null}
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="teamhome-depth-bottom">
        <div className="teamhome-depth-title">
          Position:{' '}
          <select
            className="teamhome-select teamhome-select-inline"
            value={selectedPos}
            onChange={(e) => setSelectedPos(e.target.value)}
          >
            {ALL_POSITIONS.map((p) => (
              <option key={`bot-${p}`} value={p}>
                {p}
              </option>
            ))}
          </select>
        </div>
        <div className="teamhome-depth-candidates">
          {pool.length === 0 ? (
            <div className="teamhome-roster-empty">No players can play this position yet.</div>
          ) : (
            <>
              <div
                className="teamhome-roster-row teamhome-depth-candidates-head teamhome-roster-row-attrs"
                style={{ gridTemplateColumns: depthCandidateGridCols }}
              >
                <div className="teamhome-roster-name">Name</div>
                <div className="teamhome-roster-cell">Position</div>
                <div className="teamhome-roster-cell">Off Pos</div>
                <div className="teamhome-roster-cell">Def Pos</div>
                <div className="teamhome-roster-cell">Off Rtg</div>
                <div className="teamhome-roster-cell">Def Rtg</div>
                <div className="teamhome-roster-cell">Pos Rtg</div>
                <div className="teamhome-roster-cell">Year</div>
                <div className="teamhome-roster-cell">Ht</div>
                <div className="teamhome-roster-cell">Wt</div>
                {PLAYER_ATTRIBUTE_COLUMNS_SCROLL.map((col) => (
                  <div key={col.key} className="teamhome-roster-cell teamhome-roster-attr-h" title={col.key}>
                    {col.label}
                  </div>
                ))}
              </div>
              {pool.map((p: any, i: number) => {
                const posRtg =
                  selectedPos === 'DE' ||
                  selectedPos === 'DT' ||
                  selectedPos === 'LB' ||
                  selectedPos === 'CB' ||
                  selectedPos === 'S'
                    ? Math.round(computeDefenseRating(p, selectedPos))
                    : Math.round(computeOffenseRating(p, selectedPos))
                return (
                  <div
                    key={`cand-${p?.name}-${i}`}
                    className="teamhome-roster-row teamhome-roster-row-attrs"
                    style={{ gridTemplateColumns: depthCandidateGridCols }}
                  >
                    <PlayerProfileName
                      teamName={userTeam}
                      playerName={p?.name}
                      className="teamhome-roster-name"
                      as="div"
                    />
                    <div className="teamhome-roster-cell">
                      {p?.position ?? '—'}
                      {p?.secondary_position ? ` / ${p.secondary_position}` : ''}
                    </div>
                    <div className="teamhome-roster-cell">{getPlayerSidePosition(p, 'offense')}</div>
                    <div className="teamhome-roster-cell">{getPlayerSidePosition(p, 'defense')}</div>
                    <div className="teamhome-roster-cell">
                      {getPlayerSidePosition(p, 'offense') === '—' ? '—' : getBestSideRating(p, 'offense')}
                    </div>
                    <div className="teamhome-roster-cell">
                      {getPlayerSidePosition(p, 'defense') === '—' ? '—' : getBestSideRating(p, 'defense')}
                    </div>
                    <div className="teamhome-roster-cell">{posRtg}</div>
                    <div className="teamhome-roster-cell">{formatPlayerYear(p?.year)}</div>
                    <div className="teamhome-roster-cell">{formatPlayerAttributeCell(p, 'height')}</div>
                    <div className="teamhome-roster-cell">{formatPlayerAttributeCell(p, 'weight')}</div>
                    {PLAYER_ATTRIBUTE_COLUMNS_SCROLL.map((col) => (
                      <div key={col.key} className="teamhome-roster-cell teamhome-roster-attr-cell">
                        {formatPlayerAttributeCell(p, col.key)}
                      </div>
                    ))}
                  </div>
                )
              })}
            </>
          )}
        </div>
      </div>

      <div className="depth-chart-actions">
        {onBack && (
          <button type="button" className="teamhome-playbook-confirm" onClick={onBack} disabled={saving}>
            Back
          </button>
        )}
        <button
          type="button"
          className="teamhome-playbook-confirm"
          disabled={saving || userRoster.length === 0}
          onClick={handleAutoDepthByOverall}
          title="Fill each position from eligible players: highest position rating (offense or defense for that spot), then general overall as tiebreak."
        >
          Auto depth (by position rating)
        </button>
        <button
          type="button"
          className="teamhome-playbook-confirm"
          disabled={saving}
          onClick={handleSave}
        >
          {saving ? 'Saving…' : isPreseason ? 'CONFIRM' : 'Save'}
        </button>
      </div>
      <div className="teamhome-small" style={{ marginTop: 8, maxWidth: 560 }}>
        Auto depth uses the same eligibility rules as each position’s dropdown, then ranks by that position’s offensive
        or defensive rating (tiebreak: general overall).
      </div>
    </div>
  )
}

function getCandidatesForPosition(roster: any[], pos: string) {
  const exact = roster.filter((p: any) => p?.position === pos || p?.secondary_position === pos)
  if (exact.length > 0) {
    const rate = pos === 'DE' || pos === 'DT' || pos === 'LB' || pos === 'CB' || pos === 'S'
      ? (p: any) => computeDefenseRating(p, pos)
      : (p: any) => computeOffenseRating(p, pos)
    return [...exact].sort((a, b) => rate(b) - rate(a))
  }
  return roster
    .map((p: any) => ({
      ...p,
      _rate: pos === 'DE' || pos === 'DT' || pos === 'LB' || pos === 'CB' || pos === 'S'
        ? computeDefenseRating(p, pos)
        : computeOffenseRating(p, pos),
    }))
    .sort((a: any, b: any) => (b._rate ?? 0) - (a._rate ?? 0))
}

/** Order eligible players for a position: position offense/defense rating first, then general overall. */
function sortCandidatesByPositionRating(pool: any[], pos: string): any[] {
  const isDef = pos === 'DE' || pos === 'DT' || pos === 'LB' || pos === 'CB' || pos === 'S'
  const posRate = (p: any) => (isDef ? computeDefenseRating(p, pos) : computeOffenseRating(p, pos))
  return [...pool].sort((a, b) => {
    const pr = posRate(b) - posRate(a)
    if (pr !== 0) return pr
    return computePlayerOverall(b) - computePlayerOverall(a)
  })
}

/** Full depth chart: each position filled independently from its candidate pool. */
function buildAutoDepthChartOrder(userRoster: any[]): Record<string, string[]> {
  const next: Record<string, string[]> = {}
  for (const pos of ALL_POSITIONS) {
    const slots = POSITION_DEPTH[pos] ?? 4
    const pool = getCandidatesForPosition(userRoster, pos)
    const sorted = sortCandidatesByPositionRating(pool, pos)
    const names = sorted.slice(0, slots).map((p: any) => p?.name ?? '—')
    while (names.length < slots) names.push('—')
    next[pos] = names
  }
  return next
}

const OFF_SLOTS = [
  { label: 'QB', base: 'QB' },
  { label: 'RB', base: 'RB' },
  { label: 'WR1', base: 'WR', idx: 0 },
  { label: 'WR2', base: 'WR', idx: 1 },
  { label: 'WR3', base: 'WR', idx: 2 },
  { label: 'WR4', base: 'WR', idx: 3 },
  { label: 'WR5', base: 'WR', idx: 4 },
  { label: 'TE', base: 'TE' },
  { label: 'OL1', base: 'OL', idx: 0 },
  { label: 'OL2', base: 'OL', idx: 1 },
  { label: 'OL3', base: 'OL', idx: 2 },
  { label: 'OL4', base: 'OL', idx: 3 },
  { label: 'OL5', base: 'OL', idx: 4 },
]

const DEF_SLOTS = [
  { label: 'DL1', base: 'DE', idx: 0 },
  { label: 'DL2', base: 'DE', idx: 1 },
  { label: 'DL3', base: 'DT', idx: 0 },
  { label: 'DL4', base: 'DT', idx: 1 },
  { label: 'LB1', base: 'LB', idx: 0 },
  { label: 'LB2', base: 'LB', idx: 1 },
  { label: 'LB3', base: 'LB', idx: 2 },
  { label: 'LB4', base: 'LB', idx: 3 },
  { label: 'CB1', base: 'CB', idx: 0 },
  { label: 'CB2', base: 'CB', idx: 1 },
  { label: 'CB3', base: 'CB', idx: 2 },
  { label: 'SS', base: 'S', idx: 0 },
  { label: 'FS', base: 'S', idx: 1 },
]

function buildStartersFromOrder(
  order: Record<string, string[]>,
  roster: any[],
  side: 'offense' | 'defense',
): Array<{
  label: string
  name: string
  offPosition: string
  defPosition: string
  offRating: number
  defRating: number
  measure: string
}> {
  const byName = new Map<string, any>()
  for (const p of roster ?? []) {
    if (p?.name) byName.set(p.name, p)
  }
  const slots = side === 'offense' ? OFF_SLOTS : DEF_SLOTS
  return slots.map((s) => {
    const arr = order[s.base]
    const idx = s.idx ?? 0
    const name = arr?.[idx] ?? '—'
    const player = name && name !== '—' ? byName.get(name) : null
    return {
      label: s.label,
      name: name && name !== '—' ? name : '—',
      offPosition: player ? getPlayerSidePosition(player, 'offense') : '—',
      defPosition: player ? getPlayerSidePosition(player, 'defense') : '—',
      offRating: player ? getBestSideRating(player, 'offense') : 0,
      defRating: player ? getBestSideRating(player, 'defense') : 0,
      measure: player ? formatPlayerMeasureLine(player) : '',
    }
  })
}
