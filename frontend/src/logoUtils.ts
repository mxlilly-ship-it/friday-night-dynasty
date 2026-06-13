export function teamLogoUrl(apiBase: string, teamName: string, cacheBust?: number): string {
  const base = `${apiBase}/saves/logos/${encodeURIComponent(teamName || '')}`
  if (!cacheBust) return base
  return `${base}?v=${cacheBust}`
}

export function teamStadiumUrl(apiBase: string, teamName: string, cacheBust?: number): string {
  const base = `${apiBase}/saves/stadiums/${encodeURIComponent(teamName || '')}`
  if (!cacheBust) return base
  return `${base}?v=${cacheBust}`
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

