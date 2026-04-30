export function teamLogoUrl(apiBase: string, teamName: string, cacheBust?: number): string {
  const base = `${apiBase}/saves/logos/${encodeURIComponent(teamName || '')}`
  if (!cacheBust) return base
  return `${base}?v=${cacheBust}`
}

