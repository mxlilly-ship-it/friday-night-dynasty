import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { fetchCoachGameplan, saveCoachGameplan, type GamePlanLibrary } from './browserSave'
import './CoachGameplanPage.css'
import './OffGameplanPage.css'
import './DefGameplanPage.css'
import WeeklyGameplanSections, {
  GameplanModeToggle,
  computeOffTabWarnings,
  computeDefTabWarnings,
  type GameplanTab,
  type OffGameplanTab,
} from './WeeklyGameplanSections'
import {
  defaultDefenseUsage,
  defaultOffenseUsage,
  defaultTeamScript,
  emptyDefenseCallsheet,
  emptyHalftimeSlots,
  emptyOffenseCallsheet,
  emptyPractice,
  buildSkillTargetPlayers,
  buildGameplanExportPayload,
  type HalftimeTrigger,
  type InstalledPlay,
  type SidePackage,
  type TeamScript,
} from './weeklyGameplanTypes'

type Side = 'offense' | 'defense'

const SCORE_SITUATIONS = [
  'Leading by 10+',
  'Leading by 7',
  'Leading by 3',
  'Tied',
  'Losing by 3',
  'Losing by 7',
  'Losing by 10+',
] as const

const FIELD_AREAS = [
  'Backed Up (-20 to -1)',
  'Middle of Field (-21 to 21)',
  'RedZone (20 to 5)',
  'Goal Line (5 to 1)',
] as const

const DD_BUCKETS = ['1&10', '2&10+', '2&7-10', '2&3-6', '2&1-3', '3&10+', '3&7-9', '3&3-6', '3&1-2', '4th'] as const

const OFF_CATS = ['Inside Run', 'Outside Run', 'Quick', 'Medium', 'Long', 'Play Action'] as const
const DEF_CATS = ['Zones', 'Man', 'Zone Pressure', 'Man Pressure'] as const

const OFF_CAT_INPUT_CLASS: Record<(typeof OFF_CATS)[number], string> = {
  'Inside Run': 'ogp-run',
  'Outside Run': 'ogp-run',
  Quick: 'ogp-pass',
  Medium: 'ogp-pass',
  Long: 'ogp-pass',
  'Play Action': 'ogp-pa',
}

const OFF_CAT_TH_CLASS: Record<(typeof OFF_CATS)[number], string> = {
  'Inside Run': 'ogp-run',
  'Outside Run': 'ogp-run',
  Quick: 'ogp-pass',
  Medium: 'ogp-pass',
  Long: 'ogp-pass',
  'Play Action': 'ogp-pa',
}

const OFF_GAMEPLAN_TABS: { id: OffGameplanTab; label: string }[] = [
  { id: 'gameplan', label: 'Gameplan' },
  { id: 'usage', label: 'Usage' },
  { id: 'practice', label: 'Practice' },
  { id: 'halftime', label: 'Halftime' },
  { id: 'script', label: 'Team Script' },
]

const OFF_BYE_TABS: { id: OffGameplanTab; label: string }[] = [
  { id: 'practice', label: 'Practice' },
  { id: 'script', label: 'Team Script' },
]

const DEF_CAT_INPUT_CLASS: Record<(typeof DEF_CATS)[number], string> = {
  Zones: 'dgp-zone',
  Man: 'dgp-man',
  'Zone Pressure': 'dgp-zp',
  'Man Pressure': 'dgp-mp',
}

const DEF_CAT_TH_CLASS: Record<(typeof DEF_CATS)[number], string> = {
  Zones: 'dgp-zone',
  Man: 'dgp-man',
  'Zone Pressure': 'dgp-zp',
  'Man Pressure': 'dgp-mp',
}

const DEF_GAMEPLAN_TABS: { id: GameplanTab; label: string }[] = [
  { id: 'gameplan', label: 'Gameplan' },
  { id: 'usage', label: 'Usage' },
  { id: 'practice', label: 'Practice' },
  { id: 'halftime', label: 'Halftime' },
  { id: 'script', label: 'Team Script' },
]

const DEF_BYE_TABS: { id: GameplanTab; label: string }[] = [
  { id: 'practice', label: 'Practice' },
  { id: 'script', label: 'Team Script' },
]

type PlanCell = Record<string, number>
type Plan = Record<string, Record<string, Record<string, PlanCell>>>

type Props = {
  apiBase: string
  headers: Record<string, string>
  saveId: string
  saveState: unknown
  side: Side
  onBack?: () => void
  onError: (msg: string) => void
  onSaveState?: (state: unknown) => void
}

function clampPct(n: number) {
  if (!Number.isFinite(n)) return 0
  return Math.max(0, Math.min(100, Math.round(n)))
}

function sumCell(cell: PlanCell, cats: readonly string[]) {
  return cats.reduce((acc, c) => acc + (Number(cell?.[c]) || 0), 0)
}

function downloadFile(filename: string, contentType: string, text: string) {
  const blob = new Blob([text], { type: contentType })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 250)
}

function planToCsv(side: Side, plan: Plan) {
  const cats = side === 'offense' ? OFF_CATS : DEF_CATS
  const header = ['score_situation', 'field_area', 'dd_bucket', ...cats].join(',')
  const lines: string[] = [header]
  for (const ss of SCORE_SITUATIONS) {
    for (const area of FIELD_AREAS) {
      for (const dd of DD_BUCKETS) {
        const cell = plan?.[ss]?.[area]?.[dd] ?? {}
        const row = [ss, area, dd, ...cats.map((c) => String(Number(cell?.[c]) || 0))]
          .map((v) => `"${String(v).replaceAll('"', '""')}"`)
          .join(',')
        lines.push(row)
      }
    }
  }
  return lines.join('\n')
}

function makeDefaultCell(cats: readonly string[]): PlanCell {
  const n = cats.length || 1
  const base = Math.floor(100 / n)
  const remainder = 100 - base * n
  const out: PlanCell = {}
  cats.forEach((c, i) => {
    out[c] = base + (i < remainder ? 1 : 0)
  })
  return out
}

function makeDefaultSidePackage(side: Side, grid?: Plan): SidePackage {
  const g = grid ?? makeDefaultPlan(side === 'offense' ? OFF_CATS : DEF_CATS)
  return {
    version: 1,
    gameplan_mode: 'grid',
    confirmed: false,
    grid: g as unknown as Record<string, unknown>,
    callsheet: (side === 'offense' ? emptyOffenseCallsheet() : emptyDefenseCallsheet()) as Record<string, unknown>,
    usage: side === 'offense' ? defaultOffenseUsage() : defaultDefenseUsage(),
    practice: emptyPractice(side),
    halftime: { slots: emptyHalftimeSlots() },
  }
}

function makeDefaultPlan(cats: readonly string[]): Plan {
  const p: Plan = {}
  for (const ss of SCORE_SITUATIONS) {
    p[ss] = {} as any
    for (const area of FIELD_AREAS) {
      p[ss][area] = {} as any
      for (const dd of DD_BUCKETS) {
        p[ss][area][dd] = makeDefaultCell(cats)
      }
    }
  }
  return p
}

function parseCsvLine(line: string): string[] {
  const out: string[] = []
  let cur = ''
  let inQuotes = false
  for (let i = 0; i < line.length; i++) {
    const ch = line[i]
    if (inQuotes) {
      if (ch === '"') {
        const next = line[i + 1]
        if (next === '"') {
          cur += '"'
          i += 1
        } else {
          inQuotes = false
        }
      } else {
        cur += ch
      }
    } else {
      if (ch === ',') {
        out.push(cur)
        cur = ''
      } else if (ch === '"') {
        inQuotes = true
      } else {
        cur += ch
      }
    }
  }
  out.push(cur)
  return out.map((s) => s.trim())
}

function parsePlanCsv(side: Side, csvText: string, basePlan?: Plan | null): Plan {
  const cats = side === 'offense' ? OFF_CATS : DEF_CATS
  const lines = csvText
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter((l) => l.length > 0)
  if (lines.length < 2) throw new Error('CSV is empty.')

  const header = parseCsvLine(lines[0]).map((s) => s.replace(/^"|"$/g, ''))
  const expectedHeader = ['score_situation', 'field_area', 'dd_bucket', ...cats]
  const normalizedHeader = header.map((h) => h.toLowerCase())
  const normalizedExpected = expectedHeader.map((h) => h.toLowerCase())
  for (let i = 0; i < normalizedExpected.length; i++) {
    if (normalizedHeader[i] !== normalizedExpected[i]) {
      throw new Error(`CSV header mismatch. Expected: ${expectedHeader.join(', ')}`)
    }
  }

  const plan: Plan = basePlan ? structuredClone(basePlan) : makeDefaultPlan(cats)
  for (let i = 1; i < lines.length; i++) {
    const parts = parseCsvLine(lines[i]).map((s) => s.replace(/^"|"$/g, ''))
    if (parts.length < 3 + cats.length) continue
    const ss = parts[0]
    const area = parts[1]
    const dd = parts[2]
    if (!SCORE_SITUATIONS.includes(ss as any)) continue
    if (!FIELD_AREAS.includes(area as any)) continue
    if (!DD_BUCKETS.includes(dd as any)) continue
    if (!plan[ss]) plan[ss] = {} as any
    if (!plan[ss][area]) plan[ss][area] = {} as any
    if (!plan[ss][area][dd]) plan[ss][area][dd] = {} as any
    for (let ci = 0; ci < cats.length; ci++) {
      const cat = cats[ci]
      const raw = parts[3 + ci]
      const n = clampPct(Number(raw))
      plan[ss][area][dd][cat] = n
    }
  }
  return plan
}

export default function CoachGameplanPage({
  apiBase,
  headers,
  saveId,
  saveState,
  side,
  onBack,
  onError,
  onSaveState,
}: Props) {
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [matchupKey, setMatchupKey] = useState<string | null>(null)
  const importInputRef = useRef<HTMLInputElement | null>(null)

  const [offense, setOffense] = useState<Plan | null>(null)
  const [defense, setDefense] = useState<Plan | null>(null)
  const [offenseLibrary, setOffenseLibrary] = useState<GamePlanLibrary | null>(null)
  const [defenseLibrary, setDefenseLibrary] = useState<GamePlanLibrary | null>(null)
  const [weekToWeek, setWeekToWeek] = useState(false)
  const [offensePackage, setOffensePackage] = useState<SidePackage | null>(null)
  const [defensePackage, setDefensePackage] = useState<SidePackage | null>(null)
  const [teamScript, setTeamScript] = useState<TeamScript>(defaultTeamScript())
  const [installedOffense, setInstalledOffense] = useState<InstalledPlay[]>([])
  const [installedDefense, setInstalledDefense] = useState<InstalledPlay[]>([])
  const [halftimeTriggersOff, setHalftimeTriggersOff] = useState<HalftimeTrigger[]>([])
  const [halftimeTriggersDef, setHalftimeTriggersDef] = useState<HalftimeTrigger[]>([])
  const [isByeWeek, setIsByeWeek] = useState(false)
  const [gameplanAvailable, setGameplanAvailable] = useState(true)

  const [scoreSituation, setScoreSituation] = useState<(typeof SCORE_SITUATIONS)[number]>(SCORE_SITUATIONS[3])
  const [fieldArea, setFieldArea] = useState<(typeof FIELD_AREAS)[number]>(FIELD_AREAS[1])
  const [offActiveTab, setOffActiveTab] = useState<OffGameplanTab>('gameplan')
  const [defActiveTab, setDefActiveTab] = useState<GameplanTab>('gameplan')

  const cats = useMemo(() => (side === 'offense' ? OFF_CATS : DEF_CATS), [side])
  const plan = side === 'offense' ? offense : defense
  const setPlan = side === 'offense' ? setOffense : setDefense

  const sidePackage = side === 'offense' ? offensePackage : defensePackage
  const setSidePackage = side === 'offense' ? setOffensePackage : setDefensePackage

  const targetPlayers = useMemo(() => {
    const st = saveState as {
      teams?: Record<string, unknown>[]
      user_team?: string
    }
    const team = (st?.teams ?? []).find((t) => t?.name === st?.user_team) as Record<string, unknown> | undefined
    return buildSkillTargetPlayers(team)
  }, [saveState])

  const sideLibrary = side === 'offense' ? offenseLibrary : defenseLibrary

  const saveStateRef = useRef(saveState)
  saveStateRef.current = saveState
  const onSaveStateRef = useRef(onSaveState)
  onSaveStateRef.current = onSaveState
  const headersRef = useRef(headers)
  headersRef.current = headers

  const currentWeek = Number((saveState as { current_week?: number })?.current_week ?? 0)

  const fetchPlan = useCallback(async (opts?: { showLoading?: boolean }) => {
    if (!saveId) {
      setLoading(false)
      return
    }
    const showLoading = opts?.showLoading ?? true
    if (showLoading) setLoading(true)
    setLoadError(null)
    try {
      const j = await fetchCoachGameplan(
        apiBase ?? '',
        saveId,
        saveStateRef.current,
        headersRef.current,
      )
      if (j.state) onSaveStateRef.current?.(j.state)
      setMatchupKey(j.matchup_key ?? null)
      setOffense(j.offense as Plan)
      setDefense(j.defense as Plan)
      setOffenseLibrary((j.offense_library as GamePlanLibrary | undefined) ?? null)
      setDefenseLibrary((j.defense_library as GamePlanLibrary | undefined) ?? null)
      const offGrid = j.offense as Plan
      const defGrid = j.defense as Plan
      setOffensePackage((j.offense_package as SidePackage | undefined) ?? makeDefaultSidePackage('offense', offGrid))
      setDefensePackage((j.defense_package as SidePackage | undefined) ?? makeDefaultSidePackage('defense', defGrid))
      setTeamScript({ ...defaultTeamScript(), ...((j.team_script as TeamScript | undefined) ?? {}) })
      setInstalledOffense((j.installed_plays_offense as InstalledPlay[]) ?? [])
      setInstalledDefense((j.installed_plays_defense as InstalledPlay[]) ?? [])
      setHalftimeTriggersOff((j.halftime_triggers_offense as HalftimeTrigger[]) ?? [])
      setHalftimeTriggersDef((j.halftime_triggers_defense as HalftimeTrigger[]) ?? [])
      setIsByeWeek(Boolean(j.is_bye_week))
      setGameplanAvailable(Boolean((j.meta as { gameplan_available?: boolean })?.gameplan_available ?? true))
      const wtw = j.week_to_week
      setWeekToWeek(Boolean(side === 'offense' ? wtw?.offense : wtw?.defense))
    } catch (e: unknown) {
      setLoadError(e instanceof Error ? e.message : 'Failed to load gameplan')
    } finally {
      if (showLoading) setLoading(false)
    }
  }, [apiBase, saveId])

  useEffect(() => {
    void fetchPlan({ showLoading: true })
  }, [saveId, currentWeek, side, fetchPlan])

  const rows = useMemo(() => {
    const p = plan
    if (!p) return []
    return DD_BUCKETS.map((dd) => {
      const cell = p?.[scoreSituation]?.[fieldArea]?.[dd] ?? {}
      return { dd, cell }
    })
  }, [plan, scoreSituation, fieldArea])

  const setCellValue = (dd: string, cat: string, value: number) => {
    if (!plan) return
    setPlan((prev) => {
      if (!prev) return prev
      const next: Plan = structuredClone(prev)
      if (!next[scoreSituation]) next[scoreSituation] = {} as any
      if (!next[scoreSituation][fieldArea]) next[scoreSituation][fieldArea] = {} as any
      if (!next[scoreSituation][fieldArea][dd]) next[scoreSituation][fieldArea][dd] = {} as any
      next[scoreSituation][fieldArea][dd][cat] = clampPct(value)
      return next
    })
  }

  const validateCurrentTable = () => {
    if (!plan) return { ok: false, msg: 'Missing plan' }
    for (const dd of DD_BUCKETS) {
      const cell = plan?.[scoreSituation]?.[fieldArea]?.[dd] ?? {}
      const total = sumCell(cell, cats)
      if (total !== 100) return { ok: false, msg: `Each row must total 100%. '${dd}' totals ${total}.` }
    }
    return { ok: true, msg: '' }
  }

  const duplicateToAllSituations = () => {
    if (!plan) return
    setPlan((prev) => {
      if (!prev) return prev
      const next: Plan = structuredClone(prev)
      const source = next?.[scoreSituation]
      if (!source) return next
      for (const ss of SCORE_SITUATIONS) {
        if (ss === scoreSituation) continue
        next[ss] = structuredClone(source)
      }
      return next
    })
  }

  const duplicateToAllFieldAreas = () => {
    if (!plan) return
    setPlan((prev) => {
      if (!prev) return prev
      const next: Plan = structuredClone(prev)
      const ss = next?.[scoreSituation]
      if (!ss) return next
      const sourceArea = ss?.[fieldArea]
      if (!sourceArea) return next
      for (const a of FIELD_AREAS) {
        if (a === fieldArea) continue
        ss[a] = structuredClone(sourceArea)
      }
      return next
    })
  }

  const onExportJson = (opts?: { promptName?: boolean }) => {
    const key = matchupKey ? matchupKey.replaceAll(':', '_').replaceAll(' ', '_') : 'gameplan'
    let label = `GAMEPLAN_${key}`
    if (opts?.promptName) {
      const custom = window.prompt('Name this exported gameplan (optional):', '')?.trim()
      if (custom) {
        label = custom.replace(/[^\w\s-]/g, '').replace(/\s+/g, '_').slice(0, 64) || label
      }
    }
    const payload = buildGameplanExportPayload(offensePackage, defensePackage, teamScript)
    downloadFile(`${label}.json`, 'application/json', JSON.stringify(payload, null, 2))
    onError('')
  }

  const onExportCsv = () => {
    if (!plan) return
    const key = matchupKey ? matchupKey.replaceAll(':', '_').replaceAll(' ', '_') : 'gameplan'
    downloadFile(`${side.toUpperCase()}_${key}.csv`, 'text/csv', planToCsv(side, plan))
  }

  const validateEntirePlan = (p: Plan) => {
    for (const ss of SCORE_SITUATIONS) {
      for (const area of FIELD_AREAS) {
        for (const dd of DD_BUCKETS) {
          const cell = p?.[ss]?.[area]?.[dd] ?? {}
          const total = sumCell(cell, cats)
          if (total !== 100) return { ok: false, msg: `${ss} / ${area} / ${dd} must total 100 (got ${total}).` }
        }
      }
    }
    return { ok: true, msg: '' }
  }

  const onImportClick = () => {
    importInputRef.current?.click()
  }

  const applyLibraryPlan = (source: Plan) => {
    setPlan(structuredClone(source))
    onError('')
  }

  const persistImportedPlan = async (nextPlan: Plan, rawName: string) => {
    if (!saveId) return
    const base = rawName.replace(/\.[^.]+$/, '').trim() || 'Imported plan'
    const name = window.prompt('Name this saved game plan:', base)?.trim() || base
    setBusy(true)
    try {
      const body =
        side === 'offense'
          ? { add_offense_library: { name, plan: nextPlan } }
          : { add_defense_library: { name, plan: nextPlan } }
      const j = await saveCoachGameplan(apiBase ?? '', saveId, saveStateRef.current, headersRef.current, body)
      if (j.state) onSaveStateRef.current?.(j.state)
      setOffenseLibrary(j.offense_library ?? null)
      setDefenseLibrary(j.defense_library ?? null)
      setPlan(nextPlan)
      onError('')
    } catch (e: any) {
      onError(e?.message ?? 'Failed to save imported game plan')
    } finally {
      setBusy(false)
    }
  }

  const deleteSavedPlan = async (entryId: string) => {
    if (!saveId) return
    if (!window.confirm('Delete this saved game plan from your library?')) return
    setBusy(true)
    try {
      const body =
        side === 'offense'
          ? { delete_offense_library_id: entryId }
          : { delete_defense_library_id: entryId }
      const j = await saveCoachGameplan(apiBase ?? '', saveId, saveStateRef.current, headersRef.current, body)
      if (j.state) onSaveStateRef.current?.(j.state)
      setOffenseLibrary(j.offense_library ?? null)
      setDefenseLibrary(j.defense_library ?? null)
      onError('')
    } catch (e: any) {
      onError(e?.message ?? 'Failed to delete saved game plan')
    } finally {
      setBusy(false)
    }
  }

  const onImportFile = async (file: File) => {
    const name = (file.name || '').toLowerCase()
    const text = await file.text()
    let nextPlan: Plan | null = null

    if (name.endsWith('.json') || file.type === 'application/json') {
      let j: any
      try {
        j = JSON.parse(text)
      } catch {
        throw new Error('Invalid JSON.')
      }
      // Accept either a raw plan OR a wrapper { offense, defense } export.
      const candidate = j?.[side] ?? j
      if (!candidate || typeof candidate !== 'object') throw new Error('JSON does not look like a gameplan.')
      nextPlan = candidate as Plan
    } else if (name.endsWith('.csv') || file.type.includes('csv') || file.type === 'text/plain') {
      nextPlan = parsePlanCsv(side, text, plan)
    } else {
      throw new Error('Unsupported file type. Import a .json or .csv file.')
    }

    const v = validateEntirePlan(nextPlan)
    if (!v.ok) throw new Error(v.msg)
    await persistImportedPlan(nextPlan, file.name || 'Imported plan')
  }

  const onWeekToWeekChange = async (checked: boolean) => {
    if (!saveId || !sidePackage) return
    if (checked && sidePackage.gameplan_mode === 'grid' && plan) {
      const full = validateEntirePlan(plan)
      if (!full.ok) {
        onError(`Set a valid full gameplan before enabling week-to-week carry. ${full.msg}`)
        return
      }
    }
    setWeekToWeek(checked)
    setBusy(true)
    try {
      const pkg = sidePackage.gameplan_mode === 'grid' && plan ? { ...sidePackage, grid: plan } : sidePackage
      const body =
        side === 'offense'
          ? {
              week_to_week_offense: checked,
              ...(checked ? { offense_package: pkg, team_script: teamScript } : {}),
            }
          : {
              week_to_week_defense: checked,
              ...(checked ? { defense_package: pkg, team_script: teamScript } : {}),
            }
      const j = await saveCoachGameplan(apiBase ?? '', saveId, saveStateRef.current, headersRef.current, body)
      if (j.state) onSaveStateRef.current?.(j.state)
      setMatchupKey(j.matchup_key ?? null)
      setOffense(j.offense as Plan)
      setDefense(j.defense as Plan)
      setOffensePackage((j.offense_package as SidePackage | undefined) ?? offensePackage)
      setDefensePackage((j.defense_package as SidePackage | undefined) ?? defensePackage)
      setTeamScript({ ...defaultTeamScript(), ...((j.team_script as TeamScript | undefined) ?? {}) })
      setOffenseLibrary((j.offense_library as GamePlanLibrary | undefined) ?? null)
      setDefenseLibrary((j.defense_library as GamePlanLibrary | undefined) ?? null)
      const wtw = j.week_to_week
      setWeekToWeek(Boolean(side === 'offense' ? wtw?.offense : wtw?.defense))
      onError('')
    } catch (e: unknown) {
      setWeekToWeek(!checked)
      onError(e instanceof Error ? e.message : 'Failed to save week-to-week setting')
    } finally {
      setBusy(false)
    }
  }

  const onConfirm = async () => {
    if (!saveId || !sidePackage) return
    if (!isByeWeek && !plan) return
    if (!isByeWeek && sidePackage.gameplan_mode === 'grid' && plan) {
      const full = validateEntirePlan(plan)
      if (!full.ok) {
        onError(full.msg)
        return
      }
      const v = validateCurrentTable()
      if (!v.ok) {
        onError(v.msg)
        return
      }
    }
    setBusy(true)
    try {
      const pkg = {
        ...sidePackage,
        ...(plan ? { grid: plan } : {}),
        confirmed: true,
      }
      const body =
        side === 'offense'
          ? {
              ...(plan ? { offense: plan } : {}),
              offense_package: pkg,
              team_script: teamScript,
              week_to_week_offense: weekToWeek,
              confirm_offense: true,
            }
          : {
              ...(plan ? { defense: plan } : {}),
              defense_package: pkg,
              team_script: teamScript,
              week_to_week_defense: weekToWeek,
              confirm_defense: true,
            }
      const j = await saveCoachGameplan(apiBase ?? '', saveId, saveState, headers, body)
      if (j.state) onSaveState?.(j.state)
      setMatchupKey(j.matchup_key ?? null)
      setOffense(j.offense as Plan)
      setDefense(j.defense as Plan)
      setOffensePackage((j.offense_package as SidePackage | undefined) ?? null)
      setDefensePackage((j.defense_package as SidePackage | undefined) ?? null)
      setTeamScript({ ...defaultTeamScript(), ...((j.team_script as TeamScript | undefined) ?? {}) })
      setOffenseLibrary((j.offense_library as GamePlanLibrary | undefined) ?? null)
      setDefenseLibrary((j.defense_library as GamePlanLibrary | undefined) ?? null)
      const wtw = j.week_to_week
      setWeekToWeek(Boolean(side === 'offense' ? wtw?.offense : wtw?.defense))
      onError('')
    } catch (e: any) {
      onError(e?.message ?? 'Failed to save gameplan')
    } finally {
      setBusy(false)
    }
  }

  const onAutofillCallsheet = async () => {
    if (!saveId) return
    setBusy(true)
    try {
      const j = await saveCoachGameplan(apiBase ?? '', saveId, saveStateRef.current, headersRef.current, {
        autofill_callsheet: true,
      })
      if (j.state) onSaveStateRef.current?.(j.state)
      setOffensePackage((j.offense_package as SidePackage | undefined) ?? offensePackage)
      setDefensePackage((j.defense_package as SidePackage | undefined) ?? defensePackage)
      onError('')
    } catch (e: unknown) {
      onError(e instanceof Error ? e.message : 'Autofill failed')
    } finally {
      setBusy(false)
    }
  }

  const offGridInvalid = useMemo(() => {
    if (!plan || !sidePackage || sidePackage.gameplan_mode !== 'grid') return false
    return !validateEntirePlan(plan).ok
  }, [plan, sidePackage])

  const offTabWarnings = useMemo(() => {
    if (!sidePackage) return {}
    return computeOffTabWarnings(sidePackage, targetPlayers, offGridInvalid)
  }, [sidePackage, targetPlayers, offGridInvalid])

  const defGridInvalid = useMemo(() => {
    if (!plan || !sidePackage || sidePackage.gameplan_mode !== 'grid') return false
    return !validateEntirePlan(plan).ok
  }, [plan, sidePackage])

  const defTabWarnings = useMemo(() => {
    if (!sidePackage) return {}
    return computeDefTabWarnings(sidePackage, defGridInvalid)
  }, [sidePackage, defGridInvalid])

  const renderDefenseGridEditor = () => (
    <>
      <div className="dgp-toolbar">
        <div className="dgp-field">
          <label>Situation (score margin)</label>
          <select value={scoreSituation} onChange={(e) => setScoreSituation(e.target.value as any)} disabled={busy}>
            {SCORE_SITUATIONS.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
        <div className="dgp-field">
          <label>Field area</label>
          <select value={fieldArea} onChange={(e) => setFieldArea(e.target.value as any)} disabled={busy}>
            {FIELD_AREAS.map((a) => (
              <option key={a} value={a}>
                {a}
              </option>
            ))}
          </select>
        </div>
        <div className="dgp-toolbar-actions">
          <button type="button" className="dgp-btn" onClick={onImportClick} disabled={busy}>
            Import
          </button>
          <button type="button" className="dgp-btn" onClick={duplicateToAllSituations} disabled={busy}>
            Duplicate to all situations
          </button>
          <button type="button" className="dgp-btn" onClick={duplicateToAllFieldAreas} disabled={busy}>
            Duplicate to all field areas
          </button>
          <button type="button" className="dgp-btn" onClick={() => onExportJson()} disabled={busy}>
            Export JSON
          </button>
          <button type="button" className="dgp-btn" onClick={onExportCsv} disabled={busy}>
            Export CSV
          </button>
        </div>
      </div>
      <table className="dgp-grid">
        <thead>
          <tr>
            <th style={{ textAlign: 'left' }}>D&amp;D</th>
            {DEF_CATS.map((c) => (
              <th key={c} className={DEF_CAT_TH_CLASS[c]}>
                {c.toLowerCase()}
              </th>
            ))}
            <th>Total</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const total = sumCell(r.cell, DEF_CATS)
            const bad = total !== 100
            return (
              <tr key={r.dd} className={bad ? 'invalid' : ''}>
                <td className="dgp-dd">{r.dd}</td>
                {DEF_CATS.map((c) => (
                  <td key={c}>
                    <input
                      className={DEF_CAT_INPUT_CLASS[c]}
                      inputMode="numeric"
                      value={String(Number(r.cell?.[c]) || 0)}
                      onChange={(e) => setCellValue(r.dd, c, Number(e.target.value))}
                      disabled={busy}
                    />
                  </td>
                ))}
                <td className="dgp-total">{total}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
      <p className="dgp-grid-note">
        Rows highlighted in red do not total 100% and will block Confirm and Save week to week.
      </p>
    </>
  )

  const renderDefenseLibrary = () => {
    if (!sideLibrary) return null
    return (
      <aside className="dgp-sidebar">
        <h3 className="dgp-head-font">Saved game plans</h3>
        <p className="dgp-helper">
          Pick a plan to load into this week&apos;s editor, then Confirm. Library is grid-only — percentages only.
        </p>
        <div className="dgp-plan-group">
          <div className="dgp-group-label">Built-in presets</div>
          {sideLibrary.presets.map((entry) => (
            <div key={entry.id} className="dgp-plan-item">
              <div>
                <div className="dgp-name">{entry.name}</div>
                {entry.description ? <div className="dgp-desc">{entry.description}</div> : null}
              </div>
              <button
                type="button"
                className="dgp-mini-btn"
                onClick={() => applyLibraryPlan(entry.plan as Plan)}
                disabled={busy}
              >
                Apply
              </button>
            </div>
          ))}
        </div>
        <div className="dgp-plan-group">
          <div className="dgp-group-label">My saved plans</div>
          {sideLibrary.saved.length === 0 ? (
            <p className="dgp-helper">Import JSON/CSV to add a custom plan here.</p>
          ) : (
            sideLibrary.saved.map((entry) => (
              <div key={entry.id} className="dgp-plan-item">
                <div>
                  <div className="dgp-name">{entry.name}</div>
                </div>
                <div className="dgp-plan-item-actions">
                  <button
                    type="button"
                    className="dgp-mini-btn"
                    onClick={() => applyLibraryPlan(entry.plan as Plan)}
                    disabled={busy}
                  >
                    Apply
                  </button>
                  <button
                    type="button"
                    className="dgp-mini-btn dgp-danger"
                    onClick={() => void deleteSavedPlan(entry.id)}
                    disabled={busy}
                  >
                    Delete
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </aside>
    )
  }

  const renderDefenseFooter = (confirmLabel = 'Confirm') => (
    <div className="dgp-footer-bar">
      <label className="dgp-chk-wrap" title="Reuse this side's last confirmed plan each week until you change it">
        <input
          type="checkbox"
          checked={weekToWeek}
          onChange={(e) => void onWeekToWeekChange(e.target.checked)}
          disabled={busy}
        />
        Save week to week
      </label>
      {!isByeWeek ? (
        <button type="button" className="dgp-btn" onClick={() => void onAutofillCallsheet()} disabled={busy}>
          Autofill call sheet
        </button>
      ) : null}
      <div className="dgp-spacer" />
      <button type="button" className="dgp-btn" onClick={() => void fetchPlan({ showLoading: true })} disabled={busy}>
        Reload
      </button>
      <button
        type="button"
        className="dgp-btn dgp-blue"
        title="Save OFF + DEF packages and team script for reuse. Pass targets are not included."
        onClick={() => onExportJson({ promptName: true })}
        disabled={busy}
      >
        Export gameplan (JSON)
      </button>
      <button type="button" className="dgp-btn confirm" onClick={() => void onConfirm()} disabled={busy}>
        {busy ? 'Saving…' : confirmLabel}
      </button>
    </div>
  )

  const renderOffenseGridEditor = () => (
    <>
      <div className="ogp-toolbar">
        <div className="ogp-field">
          <label>Situation (score margin)</label>
          <select value={scoreSituation} onChange={(e) => setScoreSituation(e.target.value as any)} disabled={busy}>
            {SCORE_SITUATIONS.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
        <div className="ogp-field">
          <label>Field area</label>
          <select value={fieldArea} onChange={(e) => setFieldArea(e.target.value as any)} disabled={busy}>
            {FIELD_AREAS.map((a) => (
              <option key={a} value={a}>
                {a}
              </option>
            ))}
          </select>
        </div>
        <div className="ogp-toolbar-actions">
          <button type="button" className="ogp-btn" onClick={onImportClick} disabled={busy}>
            Import
          </button>
          <button type="button" className="ogp-btn" onClick={duplicateToAllSituations} disabled={busy}>
            Duplicate to all situations
          </button>
          <button type="button" className="ogp-btn" onClick={duplicateToAllFieldAreas} disabled={busy}>
            Duplicate to all field areas
          </button>
          <button type="button" className="ogp-btn" onClick={() => onExportJson()} disabled={busy}>
            Export JSON
          </button>
          <button type="button" className="ogp-btn" onClick={onExportCsv} disabled={busy}>
            Export CSV
          </button>
        </div>
      </div>
      <table className="ogp-grid">
        <thead>
          <tr>
            <th style={{ textAlign: 'left' }}>D&amp;D</th>
            {OFF_CATS.map((c) => (
              <th key={c} className={OFF_CAT_TH_CLASS[c]}>
                {c.toLowerCase()}
              </th>
            ))}
            <th>Total</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const total = sumCell(r.cell, OFF_CATS)
            const bad = total !== 100
            return (
              <tr key={r.dd} className={bad ? 'invalid' : ''}>
                <td className="ogp-dd">{r.dd}</td>
                {OFF_CATS.map((c) => (
                  <td key={c}>
                    <input
                      className={OFF_CAT_INPUT_CLASS[c]}
                      inputMode="numeric"
                      value={String(Number(r.cell?.[c]) || 0)}
                      onChange={(e) => setCellValue(r.dd, c, Number(e.target.value))}
                      disabled={busy}
                    />
                  </td>
                ))}
                <td className="ogp-total">{total}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
      <p className="ogp-grid-note">
        Rows highlighted in red do not total 100% and will block Confirm and Save week to week.
      </p>
    </>
  )

  const renderOffenseLibrary = () => {
    if (!sideLibrary) return null
    return (
      <aside className="ogp-sidebar">
        <h3 className="ogp-head-font">Saved game plans</h3>
        <p className="ogp-helper">
          Pick a plan to load into this week&apos;s editor, then Confirm. Library is grid-only — percentages only.
        </p>
        <div className="ogp-plan-group">
          <div className="ogp-group-label">Built-in presets</div>
          {sideLibrary.presets.map((entry) => (
            <div key={entry.id} className="ogp-plan-item">
              <div>
                <div className="ogp-name">{entry.name}</div>
                {entry.description ? <div className="ogp-desc">{entry.description}</div> : null}
              </div>
              <button
                type="button"
                className="ogp-mini-btn"
                onClick={() => applyLibraryPlan(entry.plan as Plan)}
                disabled={busy}
              >
                Apply
              </button>
            </div>
          ))}
        </div>
        <div className="ogp-plan-group">
          <div className="ogp-group-label">My saved plans</div>
          {sideLibrary.saved.length === 0 ? (
            <p className="ogp-helper">Import JSON/CSV to add a custom plan here.</p>
          ) : (
            sideLibrary.saved.map((entry) => (
              <div key={entry.id} className="ogp-plan-item">
                <div>
                  <div className="ogp-name">{entry.name}</div>
                </div>
                <div className="ogp-plan-item-actions">
                  <button
                    type="button"
                    className="ogp-mini-btn"
                    onClick={() => applyLibraryPlan(entry.plan as Plan)}
                    disabled={busy}
                  >
                    Apply
                  </button>
                  <button
                    type="button"
                    className="ogp-mini-btn ogp-danger"
                    onClick={() => void deleteSavedPlan(entry.id)}
                    disabled={busy}
                  >
                    Delete
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </aside>
    )
  }

  const renderOffenseFooter = (confirmLabel = 'Confirm') => (
    <div className="ogp-footer-bar">
      <label className="ogp-chk-wrap" title="Reuse this side's last confirmed plan each week until you change it">
        <input
          type="checkbox"
          checked={weekToWeek}
          onChange={(e) => void onWeekToWeekChange(e.target.checked)}
          disabled={busy}
        />
        Save week to week
      </label>
      {!isByeWeek ? (
        <button type="button" className="ogp-btn" onClick={() => void onAutofillCallsheet()} disabled={busy}>
          Autofill call sheet
        </button>
      ) : null}
      <div className="ogp-spacer" />
      <button type="button" className="ogp-btn" onClick={() => void fetchPlan({ showLoading: true })} disabled={busy}>
        Reload
      </button>
      <button
        type="button"
        className="ogp-btn ogp-blue"
        title="Save OFF + DEF packages and team script for reuse. Pass targets are not included."
        onClick={() => onExportJson({ promptName: true })}
        disabled={busy}
      >
        Export gameplan (JSON)
      </button>
      <button type="button" className="ogp-btn confirm" onClick={() => void onConfirm()} disabled={busy}>
        {busy ? 'Saving…' : confirmLabel}
      </button>
    </div>
  )

  if (side === 'offense') {
    const tabs = isByeWeek ? OFF_BYE_TABS : OFF_GAMEPLAN_TABS
    const activeTab = tabs.some((t) => t.id === offActiveTab) ? offActiveTab : tabs[0].id

    return (
      <div className="ogp-root">
        <input
          ref={importInputRef}
          type="file"
          accept=".json,.csv,application/json,text/csv"
          style={{ display: 'none' }}
          onChange={(e) => {
            const f = e.target.files?.[0]
            e.target.value = ''
            if (!f) return
            void (async () => {
              try {
                await onImportFile(f)
                onError('')
              } catch (err: any) {
                onError(err?.message ?? 'Import failed')
              }
            })()
          }}
        />

        <header className="ogp-header">
          <button type="button" className="ogp-back-btn" onClick={onBack} disabled={!onBack}>
            ← Team Home
          </button>
          <div>
            <h1>OFF Gameplan</h1>
            <p className="ogp-subtitle">{matchupKey ? `For: ${matchupKey}` : 'For: next game'}</p>
          </div>
        </header>

        {loading ? (
          <div className="ogp-loading">Loading…</div>
        ) : loadError ? (
          <div className="ogp-card" style={{ margin: '20px 24px' }}>
            <p>{loadError}</p>
            <button type="button" className="ogp-btn" onClick={() => void fetchPlan({ showLoading: true })}>
              Retry
            </button>
          </div>
        ) : !sidePackage ? (
          <div className="ogp-loading">No gameplan loaded.</div>
        ) : (
          <div className="ogp-shell">
            {!isByeWeek ? renderOffenseLibrary() : null}
            <main className="ogp-main">
              {isByeWeek ? (
                <div className="ogp-bye-banner">Bye week — practice planning only (no opponent gameplan).</div>
              ) : null}

              <nav className="ogp-tabbar">
                {tabs.map((tab) => (
                  <button
                    key={tab.id}
                    type="button"
                    className={`ogp-tab${activeTab === tab.id ? ' active' : ''}`}
                    onClick={() => setOffActiveTab(tab.id)}
                  >
                    {tab.label}
                    {offTabWarnings[tab.id] ? <span className="ogp-dot" /> : null}
                  </button>
                ))}
              </nav>

              {isByeWeek ? (
                <WeeklyGameplanSections
                  side="offense"
                  pkg={sidePackage}
                  teamScript={teamScript}
                  installedPlays={installedOffense}
                  halftimeTriggers={halftimeTriggersOff}
                  targetPlayers={targetPlayers}
                  disabled={busy}
                  onPkgChange={(p) => setSidePackage(p)}
                  onScriptChange={setTeamScript}
                  uiVariant="off-tabs"
                  activeTab={activeTab}
                />
              ) : activeTab === 'gameplan' ? (
                <WeeklyGameplanSections
                  side="offense"
                  pkg={sidePackage}
                  teamScript={teamScript}
                  installedPlays={installedOffense}
                  halftimeTriggers={halftimeTriggersOff}
                  targetPlayers={targetPlayers}
                  disabled={busy || !gameplanAvailable}
                  onPkgChange={(p) => setSidePackage(p)}
                  onScriptChange={setTeamScript}
                  uiVariant="off-tabs"
                  activeTab="gameplan"
                  gridSlot={sidePackage.gameplan_mode === 'grid' ? renderOffenseGridEditor() : null}
                />
              ) : (
                <WeeklyGameplanSections
                  side="offense"
                  pkg={sidePackage}
                  teamScript={teamScript}
                  installedPlays={installedOffense}
                  halftimeTriggers={halftimeTriggersOff}
                  targetPlayers={targetPlayers}
                  disabled={busy || !gameplanAvailable}
                  onPkgChange={(p) => setSidePackage(p)}
                  onScriptChange={setTeamScript}
                  uiVariant="off-tabs"
                  activeTab={activeTab}
                />
              )}
            </main>
          </div>
        )}

        {!loading && sidePackage ? renderOffenseFooter(isByeWeek ? 'Confirm practice plan' : 'Confirm') : null}
      </div>
    )
  }

  const tabs = isByeWeek ? DEF_BYE_TABS : DEF_GAMEPLAN_TABS
  const activeTab = tabs.some((t) => t.id === defActiveTab) ? defActiveTab : tabs[0].id

  return (
    <div className="dgp-root">
      <input
        ref={importInputRef}
        type="file"
        accept=".json,.csv,application/json,text/csv"
        style={{ display: 'none' }}
        onChange={(e) => {
          const f = e.target.files?.[0]
          e.target.value = ''
          if (!f) return
          void (async () => {
            try {
              await onImportFile(f)
              onError('')
            } catch (err: any) {
              onError(err?.message ?? 'Import failed')
            }
          })()
        }}
      />

      <header className="dgp-header">
        <button type="button" className="dgp-back-btn" onClick={onBack} disabled={!onBack}>
          ← Team Home
        </button>
        <div>
          <h1>DEF Gameplan</h1>
          <p className="dgp-subtitle">{matchupKey ? `For: ${matchupKey}` : 'For: next game'}</p>
        </div>
      </header>

      {loading ? (
        <div className="dgp-loading">Loading…</div>
      ) : loadError ? (
        <div className="dgp-card" style={{ margin: '20px 24px' }}>
          <p>{loadError}</p>
          <button type="button" className="dgp-btn" onClick={() => void fetchPlan({ showLoading: true })}>
            Retry
          </button>
        </div>
      ) : !sidePackage ? (
        <div className="dgp-loading">No gameplan loaded.</div>
      ) : (
        <>
          {!isByeWeek && sidePackage ? (
            <div className="dgp-toplevel-mode">
              <GameplanModeToggle
                mode={sidePackage.gameplan_mode}
                disabled={busy || !gameplanAvailable}
                onChange={(mode) => setSidePackage({ ...sidePackage, gameplan_mode: mode })}
                variant="def"
              />
            </div>
          ) : null}

          <div className="dgp-shell">
            {!isByeWeek ? renderDefenseLibrary() : null}
            <main className="dgp-main">
              {isByeWeek ? (
                <div className="dgp-bye-banner">Bye week — practice planning only (no opponent gameplan).</div>
              ) : null}

              <nav className="dgp-tabbar">
                {tabs.map((tab) => (
                  <button
                    key={tab.id}
                    type="button"
                    className={`dgp-tab${activeTab === tab.id ? ' active' : ''}`}
                    onClick={() => setDefActiveTab(tab.id)}
                  >
                    {tab.label}
                    {defTabWarnings[tab.id] ? <span className="dgp-dot" /> : null}
                  </button>
                ))}
              </nav>

              {isByeWeek ? (
                <WeeklyGameplanSections
                  side="defense"
                  pkg={sidePackage}
                  teamScript={teamScript}
                  installedPlays={installedDefense}
                  halftimeTriggers={halftimeTriggersDef}
                  targetPlayers={targetPlayers}
                  disabled={busy}
                  onPkgChange={(p) => setSidePackage(p)}
                  onScriptChange={setTeamScript}
                  uiVariant="def-tabs"
                  activeTab={activeTab}
                  hideModeToggle
                />
              ) : activeTab === 'gameplan' ? (
                <WeeklyGameplanSections
                  side="defense"
                  pkg={sidePackage}
                  teamScript={teamScript}
                  installedPlays={installedDefense}
                  halftimeTriggers={halftimeTriggersDef}
                  targetPlayers={targetPlayers}
                  disabled={busy || !gameplanAvailable}
                  onPkgChange={(p) => setSidePackage(p)}
                  onScriptChange={setTeamScript}
                  uiVariant="def-tabs"
                  activeTab="gameplan"
                  hideModeToggle
                  gridSlot={sidePackage.gameplan_mode === 'grid' ? renderDefenseGridEditor() : null}
                />
              ) : (
                <WeeklyGameplanSections
                  side="defense"
                  pkg={sidePackage}
                  teamScript={teamScript}
                  installedPlays={installedDefense}
                  halftimeTriggers={halftimeTriggersDef}
                  targetPlayers={targetPlayers}
                  disabled={busy || !gameplanAvailable}
                  onPkgChange={(p) => setSidePackage(p)}
                  onScriptChange={setTeamScript}
                  uiVariant="def-tabs"
                  activeTab={activeTab}
                  hideModeToggle
                />
              )}
            </main>
          </div>
        </>
      )}

      {!loading && sidePackage ? renderDefenseFooter(isByeWeek ? 'Confirm practice plan' : 'Confirm') : null}
    </div>
  )
}

