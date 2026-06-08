import type { InstallMeta } from './playSelectionUtils'
import { DEFAULT_INSTALL_META } from './playSelectionUtils'

export type PlaySelectionPlayRow = {
  play_id: string
  name: string
  formation?: string
  pct: number
}

export type PlaySelectionCacheEntry = {
  offensive: Record<string, PlaySelectionPlayRow[]>
  defensive: Record<string, PlaySelectionPlayRow[]>
  installMeta: InstallMeta | null
}

const cache = new Map<string, PlaySelectionCacheEntry>()

export function getPlaySelectionCache(saveId: string): PlaySelectionCacheEntry | undefined {
  if (!saveId) return undefined
  return cache.get(saveId)
}

export function setPlaySelectionCache(saveId: string, entry: PlaySelectionCacheEntry): void {
  if (!saveId) return
  cache.set(saveId, entry)
}

export function patchPlaySelectionCache(
  saveId: string,
  patch: Partial<PlaySelectionCacheEntry>,
): void {
  if (!saveId) return
  const prev = cache.get(saveId)
  cache.set(saveId, {
    offensive: patch.offensive ?? prev?.offensive ?? {},
    defensive: patch.defensive ?? prev?.defensive ?? {},
    installMeta: patch.installMeta ?? prev?.installMeta ?? null,
  })
}

export function parseInstallMeta(meta: unknown): InstallMeta | null {
  if (!meta || typeof meta !== 'object') return null
  const m = meta as Record<string, unknown>
  return {
    scheme_teach: Number(m.scheme_teach ?? DEFAULT_INSTALL_META.scheme_teach),
    recommended_plays_per_category: Number(
      m.recommended_plays_per_category ?? DEFAULT_INSTALL_META.recommended_plays_per_category,
    ),
    teachable_plays_per_category: Number(
      m.teachable_plays_per_category ?? DEFAULT_INSTALL_META.teachable_plays_per_category,
    ),
    avg_football_iq: Number(m.avg_football_iq ?? DEFAULT_INSTALL_META.avg_football_iq),
    avg_coachability: Number(m.avg_coachability ?? DEFAULT_INSTALL_META.avg_coachability),
  }
}

export function parsePlaySelectionRows(side: unknown): Record<string, PlaySelectionPlayRow[]> {
  if (!side || typeof side !== 'object') return {}
  const out: Record<string, PlaySelectionPlayRow[]> = {}
  for (const [key, rows] of Object.entries(side as Record<string, unknown>)) {
    if (!Array.isArray(rows)) continue
    out[key] = rows.map((row) => {
      const r = row as Record<string, unknown>
      return {
        play_id: String(r.play_id ?? ''),
        name: String(r.name ?? r.play_id ?? ''),
        formation: r.formation != null ? String(r.formation) : undefined,
        pct: Number(r.pct ?? 0),
      }
    })
  }
  return out
}

export function cachePlaySelectionResponse(
  saveId: string,
  json: { offensive?: unknown; defensive?: unknown; install_meta?: unknown },
): PlaySelectionCacheEntry {
  const offensive = parsePlaySelectionRows(json.offensive)
  const defensive = parsePlaySelectionRows(json.defensive)
  const installMeta = parseInstallMeta(json.install_meta)
  const entry: PlaySelectionCacheEntry = { offensive, defensive, installMeta }
  setPlaySelectionCache(saveId, entry)
  return entry
}

export function hasPlaySelectionCache(saveId: string): boolean {
  const cached = getPlaySelectionCache(saveId)
  if (!cached) return false
  return (
    Object.values(cached.offensive).some((arr) => arr.length > 0) ||
    Object.values(cached.defensive).some((arr) => arr.length > 0)
  )
}
