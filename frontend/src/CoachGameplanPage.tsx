import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import './CoachGameplanPage.css'

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

type PlanCell = Record<string, number>
type Plan = Record<string, Record<string, Record<string, PlanCell>>>

type ApiResp = {
  matchup_key: string | null
  offense: Plan
  defense: Plan
  fourth_down?: { go_for_it_max_ytg?: number }
  meta?: any
}

type Props = {
  apiBase: string
  headers: Record<string, string>
  saveId: string
  side: Side
  onBack?: () => void
  onError: (msg: string) => void
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

export default function CoachGameplanPage({ apiBase, headers, saveId, side, onBack, onError }: Props) {
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [matchupKey, setMatchupKey] = useState<string | null>(null)
  const importInputRef = useRef<HTMLInputElement | null>(null)

  const [offense, setOffense] = useState<Plan | null>(null)
  const [defense, setDefense] = useState<Plan | null>(null)
  const [goForItMaxYtg, setGoForItMaxYtg] = useState<number>(2)

  const [scoreSituation, setScoreSituation] = useState<(typeof SCORE_SITUATIONS)[number]>(SCORE_SITUATIONS[3])
  const [fieldArea, setFieldArea] = useState<(typeof FIELD_AREAS)[number]>(FIELD_AREAS[1])

  const cats = useMemo(() => (side === 'offense' ? OFF_CATS : DEF_CATS), [side])
  const plan = side === 'offense' ? offense : defense
  const setPlan = side === 'offense' ? setOffense : setDefense

  const fetchPlan = useCallback(async () => {
    if (!saveId) {
      setLoading(false)
      return
    }
    setLoading(true)
    try {
      const r = await fetch(`${apiBase ?? ''}/saves/${saveId}/coach-gameplan`, { headers })
      if (!r.ok) throw new Error(await r.text())
      const j: ApiResp = await r.json()
      setMatchupKey(j.matchup_key ?? null)
      setOffense(j.offense)
      setDefense(j.defense)
      const raw = Number(j.fourth_down?.go_for_it_max_ytg)
      setGoForItMaxYtg(Number.isFinite(raw) ? Math.max(0, Math.min(10, Math.round(raw))) : 2)
      onError('')
    } catch (e: any) {
      onError(e?.message ?? 'Failed to load gameplan')
    } finally {
      setLoading(false)
    }
  }, [apiBase, saveId, headers, onError])

  useEffect(() => {
    void fetchPlan()
  }, [fetchPlan])

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

  const onExportJson = () => {
    if (!plan) return
    const key = matchupKey ? matchupKey.replaceAll(':', '_').replaceAll(' ', '_') : 'gameplan'
    downloadFile(`${side.toUpperCase()}_${key}.json`, 'application/json', JSON.stringify(plan, null, 2))
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
    setPlan(nextPlan)
  }

  const onConfirm = async () => {
    if (!saveId || !plan) return
    const v = validateCurrentTable()
    if (!v.ok) {
      onError(v.msg)
      return
    }
    setBusy(true)
    try {
      const fourth_down = { go_for_it_max_ytg: Math.max(0, Math.min(10, Math.round(Number(goForItMaxYtg) || 0))) }
      // 4th-down decisions are offensive-only. Don't allow DEF confirm to overwrite them.
      const body = side === 'offense' ? { offense: plan, fourth_down } : { defense: plan }
      const r = await fetch(`${apiBase ?? ''}/saves/${saveId}/coach-gameplan`, {
        method: 'PUT',
        headers: { ...headers, 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!r.ok) throw new Error(await r.text())
      const j: ApiResp = await r.json()
      setMatchupKey(j.matchup_key ?? null)
      setOffense(j.offense)
      setDefense(j.defense)
      const raw = Number(j.fourth_down?.go_for_it_max_ytg)
      setGoForItMaxYtg(Number.isFinite(raw) ? Math.max(0, Math.min(10, Math.round(raw))) : 2)
      onError('')
    } catch (e: any) {
      onError(e?.message ?? 'Failed to save gameplan')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="gp2-root">
      <div className="gp2-topbar">
        <button type="button" className="gp2-back" onClick={onBack} disabled={!onBack}>
          Back
        </button>
        <div className="gp2-title">{side === 'offense' ? 'OFF Gameplan' : 'DEF Gameplan'}</div>
        <div className="gp2-sub">{matchupKey ? `For: ${matchupKey}` : 'For: next game'}</div>
      </div>

      {loading ? (
        <div className="gp2-card">Loading…</div>
      ) : !plan ? (
        <div className="gp2-card">No gameplan loaded.</div>
      ) : (
        <div className="gp2-card">
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
          <div className="gp2-controls">
            <div className="gp2-control">
              <div className="gp2-label">Situation</div>
              <select className="gp2-select" value={scoreSituation} onChange={(e) => setScoreSituation(e.target.value as any)} disabled={busy}>
                {SCORE_SITUATIONS.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </div>
            <div className="gp2-control">
              <div className="gp2-label">Field area</div>
              <select className="gp2-select" value={fieldArea} onChange={(e) => setFieldArea(e.target.value as any)} disabled={busy}>
                {FIELD_AREAS.map((a) => (
                  <option key={a} value={a}>
                    {a}
                  </option>
                ))}
              </select>
            </div>
            <div className="gp2-actions">
              <button type="button" className="gp2-link" onClick={onImportClick} disabled={busy}>
                Import JSON/CSV
              </button>
              <button type="button" className="gp2-link" onClick={duplicateToAllSituations} disabled={busy}>
                Duplicate to all situations
              </button>
              <button type="button" className="gp2-link" onClick={duplicateToAllFieldAreas} disabled={busy}>
                Duplicate to all field areas
              </button>
              <button type="button" className="gp2-link" onClick={onExportJson} disabled={busy}>
                Export JSON
              </button>
              <button type="button" className="gp2-link" onClick={onExportCsv} disabled={busy}>
                Export CSV
              </button>
            </div>
          </div>

          <div className="gp2-tablewrap">
            <table className="gp2-table">
              <thead>
                <tr>
                  <th>D&amp;D</th>
                  {cats.map((c) => (
                    <th key={c}>{c}</th>
                  ))}
                  <th>Total</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => {
                  const total = sumCell(r.cell, cats)
                  const bad = total !== 100
                  return (
                    <tr key={r.dd} className={bad ? 'gp2-badrow' : ''}>
                      <td className="gp2-dd">{r.dd}</td>
                      {cats.map((c) => (
                        <td key={c}>
                          <input
                            className="gp2-input"
                            inputMode="numeric"
                            value={String(Number(r.cell?.[c]) || 0)}
                            onChange={(e) => setCellValue(r.dd, c, Number(e.target.value))}
                            disabled={busy}
                          />
                        </td>
                      ))}
                      <td className="gp2-total">{total}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          <div className="gp2-bottom">
            {side === 'offense' ? (
              <div className="gp2-fourth">
                <div className="gp2-label">4th down</div>
                <div className="gp2-fourth-row">
                  <span className="gp2-fourth-text">Go for it when yards to go ≤</span>
                  <input
                    className="gp2-input"
                    inputMode="numeric"
                    value={String(goForItMaxYtg)}
                    onChange={(e) => setGoForItMaxYtg(Math.max(0, Math.min(10, Math.round(Number(e.target.value) || 0))))}
                    disabled={busy}
                  />
                  <span className="gp2-fourth-text">(otherwise punt unless in FG range)</span>
                </div>
              </div>
            ) : null}
            <button type="button" className="gp2-confirm" onClick={() => void onConfirm()} disabled={busy}>
              {busy ? 'Saving…' : 'Confirm'}
            </button>
            <button type="button" className="gp2-refresh" onClick={() => void fetchPlan()} disabled={busy}>
              Reload
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

