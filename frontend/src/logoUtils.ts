export function teamLogoUrl(
  apiBase: string,
  teamName: string,
  cacheBust?: number,
  saveId?: string,
): string {
  const base = `${apiBase}/saves/logos/${encodeURIComponent(teamName || '')}`
  const params = new URLSearchParams()
  if (cacheBust) params.set('v', String(cacheBust))
  if (saveId) params.set('save_id', saveId)
  const q = params.toString()
  return q ? `${base}?${q}` : base
}

/** Built-in crest from data/logos/ (no per-user save overrides). */
export function teamDefaultLogoUrl(apiBase: string, teamName: string, cacheBust?: number): string {
  const base = `${apiBase}/default-logos/${encodeURIComponent(teamName || '')}`
  if (!cacheBust) return base
  return `${base}?v=${cacheBust}`
}

export function teamStadiumUrl(apiBase: string, teamName: string, cacheBust?: number): string {
  const base = `${apiBase}/saves/stadiums/${encodeURIComponent(teamName || '')}`
  if (!cacheBust) return base
  return `${base}?v=${cacheBust}`
}

/** Built-in Friday Night Lights stadium photo (used when no custom upload exists). */
export function defaultStadiumUrl(apiBase: string, cacheBust?: number): string {
  const prefix = apiBase?.trim() ? `${apiBase}/default-stadium` : '/default-stadium.png'
  if (!cacheBust) return prefix
  const sep = prefix.includes('?') ? '&' : '?'
  return `${prefix}${sep}v=${cacheBust}`
}

export function teamHelmetUrl(apiBase: string, teamName: string, cacheBust?: number): string {
  const base = `${apiBase}/saves/helmets/${encodeURIComponent(teamName || '')}`
  if (!cacheBust) return base
  return `${base}?v=${cacheBust}`
}

export type JerseyKind = 'home' | 'away' | 'alternate'

export function teamJerseyUrl(
  apiBase: string,
  teamName: string,
  kind: JerseyKind,
  cacheBust?: number,
): string {
  const base = `${apiBase}/saves/jerseys/${encodeURIComponent(teamName || '')}/${encodeURIComponent(kind)}`
  if (!cacheBust) return base
  return `${base}?v=${cacheBust}`
}

