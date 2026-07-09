import { Fragment, type ReactNode } from 'react'
import type {
  DefenseUsage,
  GameplanMode,
  HalftimeSlot,
  HalftimeTrigger,
  InstalledPlay,
  OffenseUsage,
  PracticeDay,
  SidePackage,
  TeamScript,
} from './weeklyGameplanTypes'
import {
  countCallsheetPlayIds,
  DEF_CALLSHEET_SECTIONS,
  HALFTIME_RESPONSES_DEF,
  HALFTIME_RESPONSES_OFF,
  OFF_CALLSHEET_SECTIONS,
  PRACTICE_DAYS,
  PRACTICE_DAY_BUDGET,
  PRACTICE_PILLARS_DEF,
  PRACTICE_PILLARS_OFF,
  practiceDayTotal,
  practicePillarLabel,
  RB_CARRY_OPTIONS,
  TEAM_SCRIPT_HINTS,
  type SkillTargetPlayer,
  formatSkillTargetLabel,
} from './weeklyGameplanTypes'

export type OffGameplanTab = 'gameplan' | 'usage' | 'practice' | 'halftime' | 'script'
export type GameplanTab = OffGameplanTab

type Props = {
  side: 'offense' | 'defense'
  pkg: SidePackage
  teamScript: TeamScript
  installedPlays: InstalledPlay[]
  halftimeTriggers: HalftimeTrigger[]
  targetPlayers: SkillTargetPlayer[]
  onPkgChange: (pkg: SidePackage) => void
  onScriptChange: (script: TeamScript) => void
  disabled?: boolean
  /** Hide mode radios when rendered separately at page top (defense). */
  hideModeToggle?: boolean
  /** Tabbed gameplan UI from HTML mockups. */
  uiVariant?: 'default' | 'off-tabs' | 'def-tabs'
  activeTab?: GameplanTab
  /** Grid editor slot when gameplan tab + grid mode. */
  gridSlot?: ReactNode
  /** Import full gameplan JSON (grid, call sheet, usage, practice, etc.). */
  onImportClick?: () => void
  importDisabled?: boolean
}

export function computeDefTabWarnings(
  pkg: SidePackage,
  gridInvalid: boolean,
): Partial<Record<GameplanTab, boolean>> {
  const pillars = PRACTICE_PILLARS_DEF
  let practiceOver = false
  for (const day of PRACTICE_DAYS) {
    if (practiceDayTotal(pkg.practice, day, pillars) > PRACTICE_DAY_BUDGET) {
      practiceOver = true
      break
    }
  }
  return {
    gameplan: gridInvalid,
    practice: practiceOver,
  }
}

export function computeOffTabWarnings(
  pkg: SidePackage,
  targetPlayers: SkillTargetPlayer[],
  gridInvalid: boolean,
): Partial<Record<OffGameplanTab, boolean>> {
  const pillars = PRACTICE_PILLARS_OFF
  let practiceOver = false
  for (const day of PRACTICE_DAYS) {
    if (practiceDayTotal(pkg.practice, day, pillars) > PRACTICE_DAY_BUDGET) {
      practiceOver = true
      break
    }
  }
  return {
    gameplan: gridInvalid,
    usage: targetPlayers.length === 0,
    practice: practiceOver,
  }
}

export function GameplanModeToggle({
  mode,
  onChange,
  disabled,
  variant = 'default',
}: {
  mode: GameplanMode
  onChange: (mode: GameplanMode) => void
  disabled?: boolean
  variant?: 'default' | 'off' | 'def'
}) {
  if (variant === 'off' || variant === 'def') {
    const p = variant === 'def' ? 'dgp' : 'ogp'
    const callLabel = variant === 'def' ? 'Install calls into situational buckets — sim only' : 'Install plays into situational buckets — sim only'
    return (
      <div className={`${p}-mode-toggle`}>
        <button
          type="button"
          className={`${p}-mode-opt${mode === 'grid' ? ' active' : ''}`}
          disabled={disabled}
          onClick={() => onChange('grid')}
        >
          <span className={`${p}-t`}>Grid (%)</span>
          <span className={`${p}-d`}>Situational percentage matrix</span>
        </button>
        <button
          type="button"
          className={`${p}-mode-opt${mode === 'callsheet' ? ' active' : ''}`}
          disabled={disabled}
          onClick={() => onChange('callsheet')}
        >
          <span className={`${p}-t`}>Call sheet</span>
          <span className={`${p}-d`}>{callLabel}</span>
        </button>
      </div>
    )
  }
  return (
    <div className="wg-mode">
      <label>
        <input type="radio" checked={mode === 'grid'} disabled={disabled} onChange={() => onChange('grid')} />
        Grid (%)
      </label>
      <label>
        <input type="radio" checked={mode === 'callsheet'} disabled={disabled} onChange={() => onChange('callsheet')} />
        Call sheet
      </label>
    </div>
  )
}

function Knob({
  label,
  hintKey,
  value,
  onChange,
  disabled,
  variant = 'default',
  scriptPrefix = 'ogp',
}: {
  label: string
  hintKey?: string
  value: number
  onChange: (n: number) => void
  disabled?: boolean
  variant?: 'default' | 'off' | 'off-script'
  scriptPrefix?: 'ogp' | 'dgp'
}) {
  const hint = hintKey ? TEAM_SCRIPT_HINTS[hintKey] : null
  const hintLow = hint ? `← ${hint.low}` : ''
  const hintHigh = hint ? `${hint.high} →` : ''
  const hintText =
    hint && value <= 33 ? hintLow : hint && value >= 67 ? hintHigh : hint?.mid ?? (hint ? 'Balanced (50)' : '')

  if (variant === 'off-script') {
    const p = scriptPrefix
    return (
      <div className={`${p}-script-slider`}>
        <div className={`${p}-top`}>
          <span className={`${p}-name`}>{label}</span>
          <span className={`${p}-slider-val`}>{value}</span>
        </div>
        <input
          type="range"
          min={0}
          max={100}
          value={value}
          disabled={disabled}
          onChange={(e) => onChange(Number(e.target.value))}
        />
        {hint ? (
          <div className={`${p}-slider-hints`}>
            <span>{hint.low}</span>
            <span>{hint.high}</span>
          </div>
        ) : null}
      </div>
    )
  }

  if (variant === 'off') {
    return (
      <div className="ogp-slider-wrap">
        <span className="ogp-label-font" style={{ fontSize: '11.5px', color: 'var(--ogp-text-faint)' }}>
          {label}
        </span>
        <input
          type="range"
          min={0}
          max={100}
          value={value}
          disabled={disabled}
          onChange={(e) => onChange(Number(e.target.value))}
        />
        <div className="ogp-slider-hints">
          <span>Fewer QB runs</span>
          <span>More designed QB runs</span>
        </div>
        <div className="ogp-slider-val">{value}</div>
      </div>
    )
  }

  return (
    <label className="wg-knob">
      <span className="wg-knob-label">{label}</span>
      <input
        type="range"
        min={0}
        max={100}
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(Number(e.target.value))}
      />
      <span className="wg-knob-val">{value}</span>
      {hintText ? <span className="wg-knob-hint">{hintText}</span> : null}
    </label>
  )
}

function PlaySelect({
  value,
  plays,
  playCounts,
  slotLabel,
  onChange,
  disabled,
  variant = 'default',
}: {
  value: string
  plays: InstalledPlay[]
  playCounts: Map<string, number>
  slotLabel?: string
  onChange: (v: string) => void
  disabled?: boolean
  variant?: 'default' | 'off' | 'def'
}) {
  const isDupe = Boolean(value && (playCounts.get(value) ?? 0) > 1)
  const tabbedVariant = variant === 'off' || variant === 'def'
  const p = variant === 'def' ? 'dgp' : 'ogp'
  if (tabbedVariant) {
    return (
      <div className={`${p}-cs-slot`}>
        {slotLabel ? <span className={`${p}-cs-slot-num`}>{slotLabel}</span> : null}
        <select
          className={isDupe ? `${p}-dupe` : undefined}
          value={value}
          disabled={disabled}
          onChange={(e) => onChange(e.target.value)}
        >
          <option value="">— Auto —</option>
          {plays.map((p) => {
            const n = playCounts.get(p.id) ?? 0
            const suffix = n > 0 ? ` (${n}×)` : ''
            return (
              <option key={p.id} value={p.id}>
                {p.name}
                {suffix}
              </option>
            )
          })}
        </select>
      </div>
    )
  }
  return (
    <div className="wg-play-slot">
      {slotLabel ? <span className="wg-play-slot-label">{slotLabel}</span> : null}
      <select className="wg-select" value={value} disabled={disabled} onChange={(e) => onChange(e.target.value)}>
        <option value="">— Auto —</option>
        {plays.map((p) => {
          const n = playCounts.get(p.id) ?? 0
          const suffix = n > 0 ? ` (${n}×)` : ''
          return (
            <option key={p.id} value={p.id}>
              {p.name}
              {suffix}
            </option>
          )
        })}
      </select>
    </div>
  )
}

function VerticalShotsKnob({
  value,
  disabled,
  onChange,
}: {
  value: string
  disabled?: boolean
  onChange: (v: string) => void
}) {
  const opts = [
    { id: 'conservative', label: 'Conservative', sub: 'Fewer deep shots' },
    { id: 'balanced', label: 'Balanced', sub: '' },
    { id: 'aggressive', label: 'Aggressive', sub: 'More vertical shots' },
  ]
  return (
    <div className="ogp-knob">
      <span className="ogp-label-font">Vertical shots</span>
      <div className="ogp-knob-opts">
        {opts.map((o) => (
          <button
            key={o.id}
            type="button"
            className={`ogp-knob-opt${value === o.id ? ' sel' : ''}`}
            disabled={disabled}
            onClick={() => onChange(o.id)}
          >
            {o.label}
            {o.sub ? (
              <>
                <br />
                <span style={{ color: 'var(--ogp-text-faint)', fontSize: '11px' }}>{o.sub}</span>
              </>
            ) : null}
          </button>
        ))}
      </div>
    </div>
  )
}

function PressureTendencyKnob({
  value,
  disabled,
  onChange,
}: {
  value: string
  disabled?: boolean
  onChange: (v: string) => void
}) {
  const opts = [
    { id: 'conservative', label: 'Conservative', sub: 'More coverage' },
    { id: 'balanced', label: 'Balanced', sub: '' },
    { id: 'aggressive', label: 'Aggressive', sub: 'More pressure' },
  ]
  return (
    <div className="dgp-knob">
      <span className="dgp-label-font">Pressure tendency</span>
      <div className="dgp-knob-opts">
        {opts.map((o) => (
          <button
            key={o.id}
            type="button"
            className={`dgp-knob-opt${value === o.id ? ' sel' : ''}`}
            disabled={disabled}
            onClick={() => onChange(o.id)}
          >
            {o.label}
            {o.sub ? (
              <>
                <br />
                <span style={{ color: 'var(--dgp-text-faint)', fontSize: '11px' }}>{o.sub}</span>
              </>
            ) : null}
          </button>
        ))}
      </div>
    </div>
  )
}

export default function WeeklyGameplanSections({
  side,
  pkg,
  teamScript,
  installedPlays,
  halftimeTriggers,
  targetPlayers,
  onPkgChange,
  onScriptChange,
  disabled,
  hideModeToggle,
  uiVariant = 'default',
  activeTab,
  gridSlot,
  onImportClick,
  importDisabled,
}: Props) {
  const isTabbed = uiVariant === 'off-tabs' || uiVariant === 'def-tabs'
  const isDefTabs = uiVariant === 'def-tabs'
  const tabPrefix = isDefTabs ? 'dgp' : 'ogp'
  const sections = side === 'offense' ? OFF_CALLSHEET_SECTIONS : DEF_CALLSHEET_SECTIONS
  const pillars = side === 'offense' ? PRACTICE_PILLARS_OFF : PRACTICE_PILLARS_DEF
  const cs = pkg.callsheet as Record<string, string[] | string>
  const playCounts = countCallsheetPlayIds(cs as Record<string, unknown>)
  const halftimeResponses = side === 'offense' ? HALFTIME_RESPONSES_OFF : HALFTIME_RESPONSES_DEF

  const renderImportButton = () =>
    onImportClick ? (
      <button
        type="button"
        className={`${tabPrefix}-btn`}
        title="Import JSON (full gameplan) or CSV (grid only)"
        onClick={onImportClick}
        disabled={importDisabled || disabled}
      >
        Import gameplan
      </button>
    ) : null

  const setMode = (mode: GameplanMode) => onPkgChange({ ...pkg, gameplan_mode: mode })

  const setCallSlot = (key: string, idx: number, playId: string) => {
    const arr = Array.isArray(cs[key]) ? [...(cs[key] as string[])] : []
    arr[idx] = playId
    onPkgChange({ ...pkg, callsheet: { ...cs, [key]: arr } })
  }

  const setPractice = (day: string, pillar: string, val: number) => {
    const practice = { ...pkg.practice }
    const row: PracticeDay = { ...(practice[day] ?? {}) }
    row[pillar] = Math.max(0, Math.min(50, val))
    practice[day] = row
    onPkgChange({ ...pkg, practice })
  }

  const setHalftimeSlot = (i: number, patch: Partial<HalftimeSlot>) => {
    const slots = [...(pkg.halftime?.slots ?? [])]
    slots[i] = { ...slots[i], ...patch }
    onPkgChange({ ...pkg, halftime: { slots } })
  }

  const usageOff = pkg.usage as OffenseUsage
  const usageDef = pkg.usage as DefenseUsage

  const selectedPlaySummary = [...playCounts.entries()]
    .map(([id, n]) => ({
      id,
      name: installedPlays.find((p) => p.id === id)?.name ?? id,
      n,
    }))
    .sort((a, b) => b.n - a.n || a.name.localeCompare(b.name))

  const show = (tab: GameplanTab) => !isTabbed || activeTab === tab

  const renderCallsheet = (variant: 'default' | 'off' | 'def') => {
    const tabbed = variant === 'off' || variant === 'def'
    const p = variant === 'def' ? 'dgp' : 'ogp'
    const summaryTitle = variant === 'def' ? 'Calls on your sheet' : 'Plays on your sheet'
    const emptySummary = variant === 'def' ? 'No calls installed on the sheet yet.' : 'No plays installed on the sheet yet.'
    return (
    <>
      <p className={tabbed ? `${p}-cs-note` : 'wg-note'}>
        {variant === 'def'
          ? 'Installed calls only. Empty slots run "— Auto —" from your install. All buckets rotate through filled slots — defense has no opening script.'
          : variant === 'off'
            ? 'Installed plays only. Empty slots run "— Auto —" from your install. Opening script runs sequentially on 1st/2nd & middle field until exhausted; all other buckets rotate through filled slots.'
            : 'Installed plays only. Empty = auto from install. Base D&D picks randomly; other buckets rotate.'}
      </p>
      {side === 'offense' && variant === 'off' ? (
        <VerticalShotsKnob
          value={String(cs.vertical_shots ?? 'balanced')}
          disabled={disabled}
          onChange={(v) => onPkgChange({ ...pkg, callsheet: { ...cs, vertical_shots: v } })}
        />
      ) : null}
      {side === 'defense' && variant === 'def' ? (
        <PressureTendencyKnob
          value={String(cs.pressure_tendency ?? 'balanced')}
          disabled={disabled}
          onChange={(v) => onPkgChange({ ...pkg, callsheet: { ...cs, pressure_tendency: v } })}
        />
      ) : null}
      {sections.map((sec) => (
        <div key={sec.key} className={tabbed ? `${p}-cs-bucket` : 'wg-cs-section'}>
          <div className={tabbed ? `${p}-cs-bucket-head` : 'wg-cs-title'}>
            {tabbed ? (
              <>
                <span className={`${p}-name`}>{sec.label}</span>
                <span className={`${p}-count`}>{sec.size} slots</span>
              </>
            ) : (
              sec.label
            )}
          </div>
          <div className={tabbed ? `${p}-cs-slots` : 'wg-cs-slots'}>
            {Array.from({ length: sec.size }).map((_, i) => (
              <PlaySelect
                key={`${sec.key}-${i}`}
                slotLabel={
                  sec.key === 'opening' ? String(i + 1) : tabbed ? undefined : `#${i + 1}`
                }
                variant={tabbed ? (variant === 'def' ? 'def' : 'off') : 'default'}
                value={(cs[sec.key] as string[])?.[i] ?? ''}
                plays={installedPlays}
                playCounts={playCounts}
                disabled={disabled}
                onChange={(v) => setCallSlot(sec.key, i, v)}
              />
            ))}
          </div>
        </div>
      ))}
      {side === 'offense' && !tabbed ? (
        <label className="wg-inline">
          Vertical shots
          <select
            className="wg-select"
            disabled={disabled}
            value={String(cs.vertical_shots ?? 'balanced')}
            onChange={(e) => onPkgChange({ ...pkg, callsheet: { ...cs, vertical_shots: e.target.value } })}
          >
            <option value="conservative">Conservative — fewer deep shots</option>
            <option value="balanced">Balanced</option>
            <option value="aggressive">Aggressive — more vertical shots</option>
          </select>
        </label>
      ) : null}
      {side === 'defense' && !tabbed ? (
        <label className="wg-inline">
          Pressure tendency
          <select
            className="wg-select"
            disabled={disabled}
            value={String(cs.pressure_tendency ?? 'balanced')}
            onChange={(e) => onPkgChange({ ...pkg, callsheet: { ...cs, pressure_tendency: e.target.value } })}
          >
            <option value="conservative">Conservative — more coverage</option>
            <option value="balanced">Balanced</option>
            <option value="aggressive">Aggressive — more pressure</option>
          </select>
        </label>
      ) : null}
      {tabbed ? (
        <>
          <h2 style={{ marginTop: 8, fontSize: 16, marginBottom: 8 }}>{summaryTitle}</h2>
          <div className={`${p}-cs-summary`}>
            {selectedPlaySummary.length > 0 ? (
              selectedPlaySummary.map((row) => (
                <span key={row.id} className={`${p}-item`}>
                  {row.name}
                  {row.n > 1 ? ` (${row.n}×)` : ''}
                </span>
              ))
            ) : (
              <span className={`${p}-ht-empty`}>{emptySummary}</span>
            )}
          </div>
        </>
      ) : selectedPlaySummary.length > 0 ? (
        <div className="wg-play-summary wg-play-summary--bottom">
          <div className="wg-play-summary-title">Plays on your sheet</div>
          <ul className="wg-play-summary-list">
            {selectedPlaySummary.map((row) => (
              <li key={row.id}>
                <span>{row.name}</span>
                <span className="wg-play-summary-count">{row.n}×</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </>
    )
  }

  const renderUsage = () => {
    if (side !== 'offense') {
      if (isTabbed) {
        return (
          <div className="dgp-row">
            <div className="dgp-usage-col">
              <div className="dgp-field">
                <label>Coverage</label>
                <select
                  disabled={disabled}
                  value={usageDef.coverage}
                  onChange={(e) =>
                    onPkgChange({
                      ...pkg,
                      usage: { ...usageDef, coverage: e.target.value as DefenseUsage['coverage'] },
                    })
                  }
                >
                  <option value="normal">Play normal</option>
                  <option value="bracket_1">Bracket #1 receiver</option>
                  <option value="rotation_1">Rotation toward #1</option>
                </select>
              </div>
            </div>
          </div>
        )
      }
      return (
        <label className="wg-inline">
          Coverage
          <select
            className="wg-select"
            disabled={disabled}
            value={usageDef.coverage}
            onChange={(e) =>
              onPkgChange({
                ...pkg,
                usage: { ...usageDef, coverage: e.target.value as DefenseUsage['coverage'] },
              })
            }
          >
            <option value="normal">Play normal</option>
            <option value="bracket_1">Bracket #1 receiver</option>
            <option value="rotation_1">Rotation toward #1</option>
          </select>
        </label>
      )
    }

    if (uiVariant === 'off-tabs') {
      return (
        <div className="ogp-row">
          <div className="ogp-usage-col">
            <div className="ogp-field">
              <label>RB carry split</label>
              <select
                disabled={disabled}
                value={usageOff.rb_carry_split}
                onChange={(e) => onPkgChange({ ...pkg, usage: { ...usageOff, rb_carry_split: e.target.value } })}
              >
                {RB_CARRY_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </div>
            <Knob
              variant="off"
              label="QB designed runs"
              value={usageOff.qb_designed_runs}
              disabled={disabled}
              onChange={(n) => onPkgChange({ ...pkg, usage: { ...usageOff, qb_designed_runs: n } })}
            />
          </div>
          <div className="ogp-usage-col">
            <span className="ogp-label-font" style={{ fontSize: '11.5px', color: 'var(--ogp-text-faint)' }}>
              Pass target priority
            </span>
            <p className="ogp-helper" style={{ margin: '2px 0 10px' }}>
              Order used at kickoff from depth chart. Not saved to exported templates.
            </p>
            {targetPlayers.length === 0 ? (
              <div className="ogp-warn-box">No RB/WR/TE on depth chart — set depth chart first</div>
            ) : null}
            {[0, 1, 2, 3, 4].map((i) => (
              <div key={i} className="ogp-rank-row">
                <span className="ogp-num">#{i + 1}</span>
                <select
                  disabled={disabled || targetPlayers.length === 0}
                  value={usageOff.wr_target_order[i] ?? ''}
                  onChange={(e) => {
                    const order = [...usageOff.wr_target_order]
                    while (order.length < 5) order.push('')
                    order[i] = e.target.value
                    onPkgChange({ ...pkg, usage: { ...usageOff, wr_target_order: order } })
                  }}
                >
                  <option value="">— Unset —</option>
                  {(['RB', 'WR', 'TE'] as const).map((pos) => {
                    const group = targetPlayers.filter((p) => p.chartPos === pos)
                    if (group.length === 0) return null
                    return (
                      <optgroup key={pos} label={pos}>
                        {group.map((p) => (
                          <option key={p.name} value={p.name}>
                            {formatSkillTargetLabel(p)}
                          </option>
                        ))}
                      </optgroup>
                    )
                  })}
                </select>
              </div>
            ))}
          </div>
        </div>
      )
    }

    return (
      <>
        <label className="wg-inline">
          RB carry split
          <select
            className="wg-select"
            disabled={disabled}
            value={usageOff.rb_carry_split}
            onChange={(e) => onPkgChange({ ...pkg, usage: { ...usageOff, rb_carry_split: e.target.value } })}
          >
            {RB_CARRY_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </label>
        {targetPlayers.length === 0 ? (
          <p className="wg-note wg-note--warn">
            No RB/WR/TE on depth chart — set your depth chart first (Team → Depth Chart).
          </p>
        ) : null}
        <p className="wg-note">Pass-game target priority (RB, WR, or TE). Order is used at kickoff from your depth chart.</p>
        {[0, 1, 2, 3, 4].map((i) => (
          <label key={i} className="wg-inline">
            Target #{i + 1}
            <select
              className="wg-select"
              disabled={disabled || targetPlayers.length === 0}
              value={usageOff.wr_target_order[i] ?? ''}
              onChange={(e) => {
                const order = [...usageOff.wr_target_order]
                while (order.length < 5) order.push('')
                order[i] = e.target.value
                onPkgChange({ ...pkg, usage: { ...usageOff, wr_target_order: order } })
              }}
            >
              <option value="">—</option>
              {(['RB', 'WR', 'TE'] as const).map((pos) => {
                const group = targetPlayers.filter((p) => p.chartPos === pos)
                if (group.length === 0) return null
                return (
                  <optgroup key={pos} label={pos}>
                    {group.map((p) => (
                      <option key={p.name} value={p.name}>
                        {formatSkillTargetLabel(p)}
                      </option>
                    ))}
                  </optgroup>
                )
              })}
            </select>
          </label>
        ))}
        <Knob
          label="QB designed runs"
          value={usageOff.qb_designed_runs}
          disabled={disabled}
          onChange={(n) => onPkgChange({ ...pkg, usage: { ...usageOff, qb_designed_runs: n } })}
        />
        <p className="wg-knob-hint wg-knob-hint--standalone">← Fewer QB runs · More designed QB runs →</p>
      </>
    )
  }

  const renderPractice = () => {
    if (isTabbed) {
      const p = tabPrefix
      const dimColor = isDefTabs ? 'var(--dgp-text-dim)' : 'var(--ogp-text-dim)'
      return (
        <div className={`${p}-practice-grid`}>
          <div className={`${p}-cell ${p}-head`}>Pillar</div>
          {PRACTICE_DAYS.map((day) => (
            <div key={day} className={`${p}-cell ${p}-head`}>
              {day.slice(0, 3).toUpperCase()}
            </div>
          ))}
          {pillars.map((pillar) => (
            <Fragment key={pillar}>
              <div className={`${p}-cell ${p}-pillar-label`}>{practicePillarLabel(pillar)}</div>
              {PRACTICE_DAYS.map((day) => (
                <div key={`${pillar}-${day}`} className={`${p}-cell`}>
                  <input
                    type="number"
                    min={0}
                    max={50}
                    disabled={disabled}
                    value={Number(pkg.practice?.[day]?.[pillar] ?? 0)}
                    onChange={(e) => setPractice(day, pillar, Number(e.target.value) || 0)}
                  />
                </div>
              ))}
            </Fragment>
          ))}
          <div className={`${p}-cell ${p}-pillar-label`} style={{ fontWeight: 700, color: dimColor }}>
            Daily total
          </div>
          {PRACTICE_DAYS.map((day) => {
            const used = practiceDayTotal(pkg.practice, day, pillars)
            const remaining = Math.max(0, PRACTICE_DAY_BUDGET - used)
            const over = used > PRACTICE_DAY_BUDGET
            return (
              <div key={`budget-${day}`} className={`${p}-cell ${p}-budget-cell${over ? ' over' : ' ok'}`}>
                {used} / {PRACTICE_DAY_BUDGET} used · {over ? `${used - PRACTICE_DAY_BUDGET} over` : `${remaining} available`}
              </div>
            )
          })}
        </div>
      )
    }

    return (
      <>
        {PRACTICE_DAYS.map((day) => {
          const used = practiceDayTotal(pkg.practice, day, pillars)
          const remaining = Math.max(0, PRACTICE_DAY_BUDGET - used)
          const over = used > PRACTICE_DAY_BUDGET
          return (
            <div key={day} className="wg-practice-day">
              <div className="wg-practice-day-head">
                <div className="wg-cs-title">{day.toUpperCase()}</div>
                <div className={`wg-practice-budget${over ? ' wg-practice-budget--over' : ''}`}>
                  <span>
                    <strong>{used}</strong> / {PRACTICE_DAY_BUDGET} used
                  </span>
                  <span>{over ? `${used - PRACTICE_DAY_BUDGET} over` : `${remaining} available`}</span>
                </div>
              </div>
              <div className="wg-practice-grid">
                {pillars.map((p) => (
                  <label key={p} className="wg-practice-cell">
                    <span>{practicePillarLabel(p)}</span>
                    <input
                      type="number"
                      min={0}
                      max={50}
                      disabled={disabled}
                      value={Number(pkg.practice?.[day]?.[p] ?? 0)}
                      onChange={(e) => setPractice(day, p, Number(e.target.value) || 0)}
                    />
                  </label>
                ))}
              </div>
            </div>
          )
        })}
      </>
    )
  }

  const renderHalftime = () => {
    if (isTabbed) {
      const p = tabPrefix
      return (pkg.halftime?.slots ?? []).map((slot, i) => {
        const responses = slot.trigger ? halftimeResponses[slot.trigger] : null
        return (
          <div key={i} className={`${p}-ht-slot`}>
            <div className={`${p}-ht-slot-head`}>
              <select
                disabled={disabled}
                value={slot.trigger ?? ''}
                onChange={(e) => setHalftimeSlot(i, { trigger: e.target.value || null, response: null })}
              >
                <option value="">— No trigger set —</option>
                {halftimeTriggers.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.label}
                  </option>
                ))}
              </select>
              <button
                type="button"
                className={`${p}-mini-btn`}
                disabled={disabled}
                onClick={() => setHalftimeSlot(i, { trigger: null, response: null })}
              >
                Stick to plan
              </button>
            </div>
            {slot.trigger && responses ? (
              <div className={`${p}-ht-responses`}>
                {(['A', 'B', 'C'] as const).map((r) => (
                  <button
                    key={r}
                    type="button"
                    className={`${p}-ht-resp${slot.response === r ? ' sel' : ''}`}
                    disabled={disabled}
                    onClick={() => setHalftimeSlot(i, { response: r })}
                  >
                    <span className={`${p}-letter`}>{r}</span>
                    <br />
                    {responses[r]}
                  </button>
                ))}
              </div>
            ) : (
              <span className={`${p}-ht-empty`}>Select a trigger to see response options.</span>
            )}
          </div>
        )
      })
    }

    return (pkg.halftime?.slots ?? []).map((slot, i) => {
      const responses = slot.trigger ? halftimeResponses[slot.trigger] : null
      return (
        <div key={i} className="wg-halftime-slot">
          <div className="wg-halftime-slot-head">Adjustment {i + 1}</div>
          <select
            className="wg-select"
            disabled={disabled}
            value={slot.trigger ?? ''}
            onChange={(e) => setHalftimeSlot(i, { trigger: e.target.value || null, response: null })}
          >
            <option value="">— No trigger —</option>
            {halftimeTriggers.map((t) => (
              <option key={t.id} value={t.id}>
                {t.label}
              </option>
            ))}
          </select>
          {slot.trigger && responses ? (
            <div className="wg-halftime-responses">
              {(['A', 'B', 'C'] as const).map((r) => (
                <label key={r} className={`wg-halftime-choice${slot.response === r ? ' is-selected' : ''}`}>
                  <input
                    type="radio"
                    name={`ht-${side}-${i}`}
                    disabled={disabled}
                    checked={slot.response === r}
                    onChange={() => setHalftimeSlot(i, { response: r })}
                  />
                  <span className="wg-halftime-choice-key">{r}</span>
                  <span className="wg-halftime-choice-text">{responses[r]}</span>
                </label>
              ))}
              <button
                type="button"
                className="wg-halftime-clear"
                disabled={disabled || !slot.response}
                onClick={() => setHalftimeSlot(i, { response: null })}
              >
                Stick to plan
              </button>
            </div>
          ) : slot.trigger ? (
            <p className="wg-note">Pick A, B, or C — or leave blank to keep your original plan.</p>
          ) : null}
        </div>
      )
    })
  }

  const renderScript = () => {
    const scriptKnobs =
      side === 'offense' ? (
        <>
          <Knob
            label="Pace"
            hintKey="pace"
            variant={isTabbed ? 'off-script' : 'default'}
            scriptPrefix={tabPrefix}
            value={teamScript.pace}
            disabled={disabled}
            onChange={(n) => onScriptChange({ ...teamScript, pace: n })}
          />
          <Knob
            label="Clock management"
            hintKey="clock_management"
            variant={isTabbed ? 'off-script' : 'default'}
            scriptPrefix={tabPrefix}
            value={teamScript.clock_management}
            disabled={disabled}
            onChange={(n) => onScriptChange({ ...teamScript, clock_management: n })}
          />
          <Knob
            label="Risk tolerance (4th down)"
            hintKey="risk"
            variant={isTabbed ? 'off-script' : 'default'}
            scriptPrefix={tabPrefix}
            value={teamScript.risk}
            disabled={disabled}
            onChange={(n) => onScriptChange({ ...teamScript, risk: n })}
          />
          <Knob
            label="Ball security"
            hintKey="ball_security"
            variant={isTabbed ? 'off-script' : 'default'}
            scriptPrefix={tabPrefix}
            value={teamScript.ball_security}
            disabled={disabled}
            onChange={(n) => onScriptChange({ ...teamScript, ball_security: n })}
          />
          <Knob
            label="Four-minute offense"
            hintKey="four_minute"
            variant={isTabbed ? 'off-script' : 'default'}
            scriptPrefix={tabPrefix}
            value={teamScript.four_minute}
            disabled={disabled}
            onChange={(n) => onScriptChange({ ...teamScript, four_minute: n })}
          />
          <Knob
            label="Go for 2"
            hintKey="go_for_2"
            variant={isTabbed ? 'off-script' : 'default'}
            scriptPrefix={tabPrefix}
            value={teamScript.go_for_2}
            disabled={disabled}
            onChange={(n) => onScriptChange({ ...teamScript, go_for_2: n })}
          />
          <Knob
            label="Garbage time"
            hintKey="garbage_time"
            variant={isTabbed ? 'off-script' : 'default'}
            scriptPrefix={tabPrefix}
            value={teamScript.garbage_time}
            disabled={disabled}
            onChange={(n) => onScriptChange({ ...teamScript, garbage_time: n })}
          />
          <Knob
            label="Youth reps"
            hintKey="youth_reps"
            variant={isTabbed ? 'off-script' : 'default'}
            scriptPrefix={tabPrefix}
            value={teamScript.youth_reps}
            disabled={disabled}
            onChange={(n) => onScriptChange({ ...teamScript, youth_reps: n })}
          />
        </>
      ) : (
        <>
          <Knob
            label="Pressure (script)"
            hintKey="pressure_tendency"
            variant={isTabbed ? 'off-script' : 'default'}
            scriptPrefix={tabPrefix}
            value={teamScript.pressure_tendency === 'aggressive' ? 75 : teamScript.pressure_tendency === 'conservative' ? 25 : 50}
            disabled={disabled}
            onChange={(n) =>
              onScriptChange({
                ...teamScript,
                pressure_tendency: n >= 66 ? 'aggressive' : n <= 33 ? 'conservative' : 'balanced',
              })
            }
          />
          <Knob
            label="Run fits"
            hintKey="def_run_fit"
            variant={isTabbed ? 'off-script' : 'default'}
            scriptPrefix={tabPrefix}
            value={teamScript.def_run_fit}
            disabled={disabled}
            onChange={(n) => onScriptChange({ ...teamScript, def_run_fit: n })}
          />
          <Knob
            label="Pass coverage"
            hintKey="def_coverage"
            variant={isTabbed ? 'off-script' : 'default'}
            scriptPrefix={tabPrefix}
            value={teamScript.def_coverage}
            disabled={disabled}
            onChange={(n) => onScriptChange({ ...teamScript, def_coverage: n })}
          />
          <Knob
            label="Third-down heat"
            hintKey="def_third_down"
            variant={isTabbed ? 'off-script' : 'default'}
            scriptPrefix={tabPrefix}
            value={teamScript.def_third_down}
            disabled={disabled}
            onChange={(n) => onScriptChange({ ...teamScript, def_third_down: n })}
          />
        </>
      )

    return scriptKnobs
  }

  if (isTabbed) {
    if (activeTab === 'gameplan') {
      if (isDefTabs) {
        return (
          <div className="dgp-card">
            {pkg.gameplan_mode === 'callsheet' ? (
              <div className="dgp-card-head">
                <h2>Call sheet</h2>
                {renderImportButton()}
              </div>
            ) : null}
            {pkg.gameplan_mode === 'grid' ? gridSlot : renderCallsheet('def')}
          </div>
        )
      }
      return (
        <div className="ogp-card">
          <div className="ogp-card-head">
            <h2>Gameplan mode</h2>
            {pkg.gameplan_mode === 'callsheet' ? renderImportButton() : null}
          </div>
          <p className="ogp-helper">
            Choose how this week&apos;s offense is built. Grid drives percentages by situation; Call sheet installs specific plays for sim games.
          </p>
          {!hideModeToggle ? (
            <GameplanModeToggle mode={pkg.gameplan_mode} onChange={setMode} disabled={disabled} variant="off" />
          ) : null}
          {pkg.gameplan_mode === 'grid' ? gridSlot : renderCallsheet('off')}
        </div>
      )
    }

    const offCardMeta: Record<Exclude<GameplanTab, 'gameplan'>, { title: string; helper: string }> = {
      usage: {
        title: 'Usage',
        helper: 'How touches and targets are distributed across your depth chart.',
      },
      practice: {
        title: 'Practice',
        helper: `Max ${PRACTICE_DAY_BUDGET} points per day across all pillars. Monday through Thursday.`,
      },
      halftime: {
        title: 'Halftime adjustments',
        helper: 'If a trigger fires at halftime, the matching response is applied. Leave blank to stick to plan. Sim games only.',
      },
      script: {
        title: 'Team game script',
        helper: 'Offensive game-week tendencies — tempo, clock, risk, and rotation. Sim only.',
      },
    }

    const defCardMeta: Record<Exclude<GameplanTab, 'gameplan'>, { title: string; helper: string }> = {
      usage: {
        title: 'Usage',
        helper: "How your secondary plays technique against the opponent's top target.",
      },
      practice: {
        title: 'Practice',
        helper: `Max ${PRACTICE_DAY_BUDGET} points per day across all pillars. Monday through Thursday.`,
      },
      halftime: {
        title: 'Halftime adjustments',
        helper: 'If a trigger fires at halftime, the matching response is applied. Leave blank to stick to plan. Sim games only.',
      },
      script: {
        title: 'Team game script',
        helper: 'Defensive game-week tendencies — pressure, run fits, coverage, and third-down heat. Sim only.',
      },
    }

    if (!activeTab) return null
    const cardMeta = isDefTabs ? defCardMeta : offCardMeta
    const meta = cardMeta[activeTab]

    return (
      <div className={`${tabPrefix}-card`}>
        <div className={`${tabPrefix}-card-head`}>
          <h2>{meta.title}</h2>
          {renderImportButton()}
        </div>
        <p className={`${tabPrefix}-helper`}>{meta.helper}</p>
        {activeTab === 'usage' ? renderUsage() : null}
        {activeTab === 'practice' ? renderPractice() : null}
        {activeTab === 'halftime' ? renderHalftime() : null}
        {activeTab === 'script' ? renderScript() : null}
      </div>
    )
  }

  return (
    <div className="wg-sections">
      {!hideModeToggle ? (
        <section className="wg-block">
          <h3 className="wg-h3">Gameplan mode</h3>
          <GameplanModeToggle mode={pkg.gameplan_mode} onChange={setMode} disabled={disabled} />
        </section>
      ) : null}

      {pkg.gameplan_mode === 'callsheet' && show('gameplan') ? (
        <section className="wg-block">
          <h3 className="wg-h3">Call sheet</h3>
          {renderCallsheet('default')}
        </section>
      ) : null}

      {show('usage') ? (
        <section className="wg-block">
          <h3 className="wg-h3">Usage</h3>
          {renderUsage()}
        </section>
      ) : null}

      {show('practice') ? (
        <section className="wg-block">
          <h3 className="wg-h3">Practice ({PRACTICE_DAY_BUDGET} pts / day)</h3>
          <p className="wg-note">
            Distribute up to {PRACTICE_DAY_BUDGET} points per day across pillars. Extra points over {PRACTICE_DAY_BUDGET} will be scaled down on save.
          </p>
          {renderPractice()}
        </section>
      ) : null}

      {show('halftime') ? (
        <section className="wg-block">
          <h3 className="wg-h3">Halftime adjustments (sim)</h3>
          <p className="wg-note">If the trigger fires at halftime, apply the response. Leave response blank to stick to your gameplan.</p>
          {renderHalftime()}
        </section>
      ) : null}

      {show('script') ? (
        <section className="wg-block">
          <h3 className="wg-h3">Team game script</h3>
          <p className="wg-note">Sliders affect sim only. Low = left, high = right.</p>
          {renderScript()}
        </section>
      ) : null}
    </div>
  )
}
