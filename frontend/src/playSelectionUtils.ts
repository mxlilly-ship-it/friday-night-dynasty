/** Mirrors systems/play_selection.py — keep in sync for live install meter. */

export const ACTIVE_PLAY_PCT_THRESHOLD = 0.01

export const UNDERSTANDING_GRADES = [
  'A+', 'A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D+', 'D', 'D-', 'F+', 'F', 'F-',
] as const

const UNDERSTANDING_SCORE_BANDS: [number, number][] = [
  [93, 100], [90, 92], [87, 89], [83, 86], [80, 82], [77, 79], [73, 76], [70, 72],
  [67, 69], [63, 66], [60, 62], [57, 59], [53, 56], [50, 52], [0, 49],
]

export type InstallMeta = {
  scheme_teach: number
  recommended_plays_per_category: number
  teachable_plays_per_category: number
  avg_football_iq: number
  avg_coachability: number
}

export type PlayPctEntry = { play_id: string; pct: number }

export type ProjectedInstallSummary = {
  overall_grade: string
  offensive_pct_learned: number
  defensive_pct_learned: number
  offensive_active_plays_per_category: number
  defensive_active_plays_per_category: number
}

export type InstallBand = 'focused' | 'stretch' | 'overload'

export function isActivePlayPct(pct: number): boolean {
  return Number.isFinite(pct) && pct > ACTIVE_PLAY_PCT_THRESHOLD
}

export function countActivePlays(entries: readonly PlayPctEntry[]): number {
  return entries.filter((p) => isActivePlayPct(p.pct)).length
}

export function filterActivePlayEntries(entries: readonly PlayPctEntry[]): PlayPctEntry[] {
  return entries.filter((p) => isActivePlayPct(p.pct))
}

export function recommendedPlaysPerCategory(schemeTeach: number): number {
  const st = Math.max(1, Math.min(10, Math.round(schemeTeach)))
  const n = 2 + ((st - 1) * 4) / 9
  return Math.max(2, Math.min(6, Math.round(n)))
}

export function teachablePlaysPerCategory(meta: InstallMeta): number {
  const teachingScore = (meta.scheme_teach * 10 + meta.avg_football_iq + meta.avg_coachability) / 3
  const clamped = Math.max(0, Math.min(100, teachingScore))
  return 2 + (clamped / 100) * 8
}

export function understandingScoreFromOverload(overload: number): number {
  const raw = 100 - (overload - 0.7) * 45
  return Math.max(0, Math.min(100, raw))
}

export function scoreToGrade(score: number): string {
  for (let i = 0; i < UNDERSTANDING_SCORE_BANDS.length; i++) {
    const [lo, hi] = UNDERSTANDING_SCORE_BANDS[i]
    if (score >= lo && score <= hi) return UNDERSTANDING_GRADES[i]
  }
  return 'F-'
}

export function avgActivePlaysPerCategory(
  categoryKeys: readonly string[],
  selection: Record<string, readonly PlayPctEntry[]>,
): number {
  const counts = categoryKeys
    .map((key) => countActivePlays(selection[key] || []))
    .filter((n) => n > 0)
  if (!counts.length) return 0
  return counts.reduce((a, b) => a + b, 0) / counts.length
}

export function computeProjectedInstallSummary(
  meta: InstallMeta,
  offensive: Record<string, readonly PlayPctEntry[]>,
  defensive: Record<string, readonly PlayPctEntry[]>,
  offCategoryKeys: readonly string[],
  defCategoryKeys: readonly string[],
): ProjectedInstallSummary {
  const teachable = meta.teachable_plays_per_category || teachablePlaysPerCategory(meta)
  const avgOff = avgActivePlaysPerCategory(offCategoryKeys, offensive)
  const avgDef = avgActivePlaysPerCategory(defCategoryKeys, defensive)

  const sidePct = (avgPerCat: number) => {
    if (avgPerCat <= 0 || teachable <= 0) return 0
    return Math.round(understandingScoreFromOverload(avgPerCat / teachable))
  }

  let avgPlaysPerCat = 0
  if (avgOff > 0 && avgDef > 0) avgPlaysPerCat = (avgOff + avgDef) / 2
  else if (avgOff > 0) avgPlaysPerCat = avgOff
  else if (avgDef > 0) avgPlaysPerCat = avgDef

  const overload = teachable > 0 ? avgPlaysPerCat / teachable : 2
  const overallScore = understandingScoreFromOverload(overload)

  return {
    overall_grade: scoreToGrade(overallScore),
    offensive_pct_learned: sidePct(avgOff),
    defensive_pct_learned: sidePct(avgDef),
    offensive_active_plays_per_category: Math.round(avgOff * 10) / 10,
    defensive_active_plays_per_category: Math.round(avgDef * 10) / 10,
  }
}

export function categoryInstallBand(
  activeCount: number,
  recommended: number,
  teachable: number,
): InstallBand {
  if (activeCount <= 0) return 'focused'
  if (activeCount <= recommended) return 'focused'
  const overload = teachable > 0 ? activeCount / teachable : 2
  if (overload <= 1.25) return 'stretch'
  return 'overload'
}

export function installBandLabel(band: InstallBand): string {
  if (band === 'focused') return 'Focused'
  if (band === 'stretch') return 'Stretch'
  return 'Overload'
}

export const DEFAULT_INSTALL_META: InstallMeta = {
  scheme_teach: 5,
  recommended_plays_per_category: 4,
  teachable_plays_per_category: 6,
  avg_football_iq: 50,
  avg_coachability: 50,
}
