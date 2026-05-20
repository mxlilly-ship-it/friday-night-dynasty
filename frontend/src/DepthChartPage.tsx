import { useCallback, useEffect, useMemo, useState } from 'react'
import './TeamHomePage.css'
import {
  CANONICAL_STORAGE_KEYS,
  POSITION_DEPTH,
  findDisplaySlot,
  getCoachPlaybooksFromSave,
  getPlaybookDepthLayout,
  getSlotPlayerName,
  setSlotPlayerName,
  type DepthDisplaySlot,
  type PlaybookDepthLayout,
} from './depthChartPlaybookLayouts'
import {
  PLAYER_ATTRIBUTE_COLUMNS_SCROLL,
  formatPlayerAttributeCell,
  formatPlayerMeasureLine,
  rosterDepthTableGridTemplateColumns,
} from './playerAttributes'
import { PlayerProfileName } from './PlayerProfileContext'

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
  const offense = ['QB', 'RB', 'WR', 'OL', 'TE'] as const
  const defense = ['DE', 'DT', 'LB', 'CB', 'S'] as const
  const allowed = side === 'offense' ? offense : defense
  const primary = String(p?.position ?? '')
  const secondary = String(p?.secondary_position ?? '')
  if ((allowed as readonly string[]).includes(primary)) return primary
  if ((allowed as readonly string[]).includes(secondary)) return secondary
  return '—'
}

function getBestSideRating(p: any, side: 'offense' | 'defense') {
  const offense = ['QB', 'RB', 'WR', 'OL', 'TE'] as const
  const defense = ['DE', 'DT', 'LB', 'CB', 'S'] as const
  const allowed = side === 'offense' ? offense : defense
  const rate = side === 'offense' ? computeOffenseRating : computeDefenseRating
  const candidates = [String(p?.position ?? ''), String(p?.secondary_position ?? '')].filter((pos) =>
    (allowed as readonly string[]).includes(pos),
  )
  if (candidates.length === 0) return 0
  let best = 0
  for (const pos of candidates) best = Math.max(best, rate(p, pos))
  return Math.round(best)
}

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

function isDefensiveRatingKey(key: string) {
  return key === 'DE' || key === 'DT' || key === 'LB' || key === 'CB' || key === 'S'
}

function getCandidatesForRatingKey(roster: any[], ratingKey: string) {
  const exact = roster.filter((p: any) => p?.position === ratingKey || p?.secondary_position === ratingKey)
  if (exact.length > 0) {
    const rate = isDefensiveRatingKey(ratingKey)
      ? (p: any) => computeDefenseRating(p, ratingKey)
      : (p: any) => computeOffenseRating(p, ratingKey)
    return [...exact].sort((a, b) => rate(b) - rate(a))
  }
  return roster
    .map((p: any) => ({
      ...p,
      _rate: isDefensiveRatingKey(ratingKey)
        ? computeDefenseRating(p, ratingKey)
        : computeOffenseRating(p, ratingKey),
    }))
    .sort((a: any, b: any) => (b._rate ?? 0) - (a._rate ?? 0))
}

function sortCandidatesByPositionRating(pool: any[], ratingKey: string): any[] {
  const isDef = isDefensiveRatingKey(ratingKey)
  const posRate = (p: any) => (isDef ? computeDefenseRating(p, ratingKey) : computeOffenseRating(p, ratingKey))
  return [...pool].sort((a, b) => {
    const pr = posRate(b) - posRate(a)
    if (pr !== 0) return pr
    return computePlayerOverall(b) - computePlayerOverall(a)
  })
}

function buildAutoDepthChartOrder(userRoster: any[]): Record<string, string[]> {
  const next: Record<string, string[]> = {}
  for (const pos of CANONICAL_STORAGE_KEYS) {
    const slots = POSITION_DEPTH[pos] ?? 4
    const pool = getCandidatesForRatingKey(userRoster, pos)
    const sorted = sortCandidatesByPositionRating(pool, pos)
    const names = sorted.slice(0, slots).map((p: any) => p?.name ?? '—')
    while (names.length < slots) names.push('—')
    next[pos] = names
  }
  return next
}

function ensureFullCanonicalOrder(
  userRoster: any[],
  savedOrder: Record<string, string[]>,
): Record<string, string[]> {
  const init: Record<string, string[]> = {}
  for (const pos of CANONICAL_STORAGE_KEYS) {
    const slots = POSITION_DEPTH[pos] ?? 4
    const pool = getCandidatesForRatingKey(userRoster, pos)
    const saved = savedOrder[pos]
    if (saved && Array.isArray(saved)) {
      init[pos] = saved.filter((n) => typeof n === 'string').slice(0, slots)
    } else {
      init[pos] = pool.slice(0, slots).map((p: any) => p?.name ?? '—')
    }
    while (init[pos].length < slots) init[pos].push('—')
  }
  return init
}

function buildStartersFromLayout(
  order: Record<string, string[]>,
  roster: any[],
  slots: DepthDisplaySlot[],
  userTeam: string,
) {
  const byName = new Map<string, any>()
  for (const p of roster ?? []) {
    if (p?.name) byName.set(p.name, p)
  }
  return slots.map((slot) => {
    const name = getSlotPlayerName(order, slot)
    const player = name && name !== '—' ? byName.get(name) : null
    return {
      slot,
      name: name && name !== '—' ? name : '—',
      offPosition: player ? getPlayerSidePosition(player, 'offense') : '—',
      defPosition: player ? getPlayerSidePosition(player, 'defense') : '—',
      offRating: player ? getBestSideRating(player, 'offense') : 0,
      defRating: player ? getBestSideRating(player, 'defense') : 0,
      measure: player ? formatPlayerMeasureLine(player) : '',
      userTeam,
    }
  })
}

function SlotSelect({
  layout,
  slot,
  order,
  roster,
  onChange,
}: {
  layout: PlaybookDepthLayout
  slot: DepthDisplaySlot
  order: Record<string, string[]>
  roster: any[]
  onChange: (name: string) => void
}) {
  const pool = useMemo(() => getCandidatesForRatingKey(roster, slot.ratingKey), [roster, slot.ratingKey])
  const value = getSlotPlayerName(order, slot)

  return (
    <div className="teamhome-depth-item depth-slot-row">
      <span className="teamhome-depth-slot-label">{slot.label}</span>
      <select
        className="teamhome-select-inline depth-slot-select"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        aria-label={`${slot.label} starter (${layout.offensivePlaybook} / ${layout.defensivePlaybook})`}
      >
        <option value="—">—</option>
        {pool.map((p: any, i: number) => (
          <option key={`${slot.id}-${p?.name ?? i}`} value={p?.name ?? '—'}>
            {p?.name ?? '—'}
          </option>
        ))}
      </select>
    </div>
  )
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

  const coachPlaybooks = useMemo(() => getCoachPlaybooksFromSave(saveState, userTeam), [saveState, userTeam])
  const layout = useMemo(
    () => getPlaybookDepthLayout(coachPlaybooks.offensive, coachPlaybooks.defensive),
    [coachPlaybooks],
  )

  const [localOrder, setLocalOrder] = useState<Record<string, string[]>>({})
  const [selectedSlotId, setSelectedSlotId] = useState<string>('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    setLocalOrder(ensureFullCanonicalOrder(userRoster, savedOrder))
  }, [userRoster, savedOrder])

  useEffect(() => {
    const first = layout.offense[0]?.id ?? layout.defense[0]?.id ?? ''
    setSelectedSlotId((prev) => (findDisplaySlot(layout, prev) ? prev : first))
  }, [layout])

  const selectedSlot = useMemo(
    () => (selectedSlotId ? findDisplaySlot(layout, selectedSlotId) : undefined),
    [layout, selectedSlotId],
  )

  const pool = useMemo(
    () => (selectedSlot ? getCandidatesForRatingKey(userRoster, selectedSlot.ratingKey) : []),
    [userRoster, selectedSlot],
  )

  const offensiveStarters = useMemo(
    () => buildStartersFromLayout(localOrder, userRoster, layout.offense, userTeam),
    [localOrder, userRoster, layout.offense, userTeam],
  )
  const defensiveStarters = useMemo(
    () => buildStartersFromLayout(localOrder, userRoster, layout.defense, userTeam),
    [localOrder, userRoster, layout.defense, userTeam],
  )

  const handleSlotChange = useCallback(
    (slot: DepthDisplaySlot, playerName: string) => {
      setLocalOrder((prev) => setSlotPlayerName(prev, slot, playerName))
    },
    [],
  )

  const handleSave = useCallback(async () => {
    setSaving(true)
    try {
      const toSave: Record<string, string[]> = {}
      for (const pos of CANONICAL_STORAGE_KEYS) {
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

  const renderSlotOptions = (side: 'offense' | 'defense') => {
    const slots = side === 'offense' ? layout.offense : layout.defense
    const playbook = side === 'offense' ? layout.offensivePlaybook : layout.defensivePlaybook
    return (
      <optgroup key={side} label={`${side === 'offense' ? 'Offense' : 'Defense'} (${playbook})`}>
        {slots.map((slot) => (
          <option key={slot.id} value={slot.id}>
            {slot.label}
          </option>
        ))}
      </optgroup>
    )
  }

  return (
    <div className="teamhome-depth-shell">
      <p className="teamhome-depth-playbook-banner teamhome-small">
        Base personnel for your playbooks:{' '}
        <strong>{layout.offensivePlaybook}</strong> ({layout.baseOffenseFormation}) ·{' '}
        <strong>{layout.defensivePlaybook}</strong> ({layout.baseDefenseFormation}). Slots map to your saved depth at
        each position; subs and packages still use full position depth behind these starters.
      </p>

      <div className="teamhome-depth-top">
        <div className="teamhome-depth-col">
          <div className="teamhome-depth-title">
            Starter:{' '}
            <select
              className="teamhome-select teamhome-select-inline"
              value={selectedSlotId}
              onChange={(e) => setSelectedSlotId(e.target.value)}
            >
              {renderSlotOptions('offense')}
              {renderSlotOptions('defense')}
            </select>
          </div>
          {selectedSlot ? (
            <div className="teamhome-depth-stack">
              <SlotSelect
                layout={layout}
                slot={selectedSlot}
                order={localOrder}
                roster={userRoster}
                onChange={(name) => handleSlotChange(selectedSlot, name)}
              />
            </div>
          ) : null}
        </div>

        <div className="teamhome-depth-col">
          <div className="teamhome-depth-title">Offense — {layout.offensivePlaybook}</div>
          <div className="teamhome-depth-stack teamhome-depth-stack--compact">
            {offensiveStarters.map((s) => (
              <div
                key={s.slot.id}
                className={`teamhome-depth-item teamhome-depth-item--clickable${selectedSlotId === s.slot.id ? ' teamhome-depth-item--active' : ''}`}
                role="button"
                tabIndex={0}
                onClick={() => setSelectedSlotId(s.slot.id)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    setSelectedSlotId(s.slot.id)
                  }
                }}
              >
                <span className="teamhome-depth-slot-label">{s.slot.label}:</span>{' '}
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
          <div className="teamhome-depth-title">Defense — {layout.defensivePlaybook}</div>
          <div className="teamhome-depth-stack teamhome-depth-stack--compact">
            {defensiveStarters.map((s) => (
              <div
                key={s.slot.id}
                className={`teamhome-depth-item teamhome-depth-item--clickable${selectedSlotId === s.slot.id ? ' teamhome-depth-item--active' : ''}`}
                role="button"
                tabIndex={0}
                onClick={() => setSelectedSlotId(s.slot.id)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    setSelectedSlotId(s.slot.id)
                  }
                }}
              >
                <span className="teamhome-depth-slot-label">{s.slot.label}:</span>{' '}
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
          Candidates for{' '}
          <strong>{selectedSlot?.label ?? '—'}</strong>
          {selectedSlot ? (
            <span className="teamhome-small" style={{ marginLeft: 8, opacity: 0.75 }}>
              (rates as {selectedSlot.ratingKey})
            </span>
          ) : null}
        </div>
        <div className="teamhome-depth-candidates">
          {pool.length === 0 ? (
            <div className="teamhome-roster-empty">No players match this spot yet.</div>
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
                const ratingKey = selectedSlot?.ratingKey ?? 'QB'
                const posRtg = isDefensiveRatingKey(ratingKey)
                  ? Math.round(computeDefenseRating(p, ratingKey))
                  : Math.round(computeOffenseRating(p, ratingKey))
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
          title="Fill full position depth (all backup slots), then map to playbook starters."
        >
          Auto depth (by position rating)
        </button>
        <button type="button" className="teamhome-playbook-confirm" disabled={saving} onClick={handleSave}>
          {saving ? 'Saving…' : isPreseason ? 'CONFIRM' : 'Save'}
        </button>
      </div>
      <div className="teamhome-small" style={{ marginTop: 8, maxWidth: 640 }}>
        Chart layout follows your selected playbooks. Under the hood, data is still stored by position group (e.g. FB
        uses the RB depth list). Auto depth fills every backup slot; click a starter on the right to edit that spot.
      </div>
    </div>
  )
}
