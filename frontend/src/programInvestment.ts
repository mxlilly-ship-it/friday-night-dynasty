/** Shared helpers for offseason program pillar investment (culture / facilities / boosters). */

export const UPGRADE_COST_BY_LEVEL: Record<number, number> = {
  1: 100,
  2: 300,
  3: 500,
  4: 800,
  5: 1200,
  6: 1500,
  7: 1900,
  8: 2400,
  9: 3000,
}

export const PILLAR_CHIP_VALUES = [5, 25, 100] as const

export const PILLAR_CUMULATIVE_PP_MAX = (() => {
  let s = 0
  for (let k = 1; k <= 9; k += 1) s += UPGRADE_COST_BY_LEVEL[k] ?? 3000
  return s
})()

export function clampImprovementLevel(raw: number, fallback: number): number {
  const x = Number(raw)
  const base = Number.isFinite(x) ? x : fallback
  return Math.max(1, Math.min(10, Math.floor(base)))
}

export function pillarCumulativePpValue(level: number, progressPts: number): number {
  const L = clampImprovementLevel(level, 5)
  const pts = Math.max(0, Math.min(3500, Math.floor(Number(progressPts) || 0)))
  let total = 0
  for (let k = 1; k < L; k += 1) total += UPGRADE_COST_BY_LEVEL[k] ?? 3000
  if (L < 10) {
    const cap = UPGRADE_COST_BY_LEVEL[L] ?? 3000
    total += Math.min(pts, cap)
  }
  return total
}

export function pillarStateFromCumulativePpValue(target: number): { level: number; progressPts: number } {
  let v = Math.max(0, Math.min(PILLAR_CUMULATIVE_PP_MAX, Math.floor(Number(target) || 0)))
  let L = 1
  while (L < 10) {
    const need = UPGRADE_COST_BY_LEVEL[L] ?? 3000
    if (v < need) return { level: L, progressPts: v }
    v -= need
    L += 1
  }
  return { level: 10, progressPts: 0 }
}

export function formatProgramPpDelta(n: number): string {
  const v = Number(n)
  if (!Number.isFinite(v)) return '—'
  if (v > 0) return `+${Math.round(v)}`
  if (v < 0) return String(Math.round(v))
  return '0'
}

export type PillarRingDisplay = {
  level: number
  nextLevel: number
  progress: number
  required: number
  pct: number
  deficit: boolean
}

export function pillarRingDisplay(targetCumulative: number, fromCumulative: number): PillarRingDisplay {
  const { level, progressPts } = pillarStateFromCumulativePpValue(targetCumulative)
  const deficit = targetCumulative < fromCumulative
  if (level >= 10) {
    return { level: 10, nextLevel: 10, progress: 0, required: 0, pct: 100, deficit }
  }
  const required = UPGRADE_COST_BY_LEVEL[level] ?? 3000
  const pct = required > 0 ? Math.round((progressPts / required) * 100) : 0
  return {
    level,
    nextLevel: level + 1,
    progress: progressPts,
    required,
    pct: Math.max(0, Math.min(100, pct)),
    deficit,
  }
}

export type ProgramInvestmentPillar = {
  id: string
  label: string
  badge: string
  accent: string
  accentDim: string
  fromCumulative: number
  targetCumulative: number
}

export const PROGRAM_INVESTMENT_PILLAR_THEME: Record<
  string,
  { badge: string; accent: string; accentDim: string }
> = {
  facilities: { badge: 'F', accent: '#3FB6D8', accentDim: '#1E4955' },
  culture: { badge: 'C', accent: '#9B6FE0', accentDim: '#3C2C5C' },
  boosters: { badge: 'B', accent: '#C9A227', accentDim: '#4A3D14' },
}
