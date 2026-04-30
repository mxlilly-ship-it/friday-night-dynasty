/** Mirror backend `_normalize_name`: lowercase, alphanumeric only. */
export function normalizeNameKey(s: string): string {
  return String(s || '')
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]/g, '')
}

function stemVariants(stem: string): string[] {
  const stemTrim = stem.trim()
  if (!stemTrim) return []
  const variants = [stemTrim]
  for (const suffix of ['_logo', '-logo', '_LOGO', '-LOGO', ' logo']) {
    if (stemTrim.length > suffix.length && stemTrim.toLowerCase().endsWith(suffix.toLowerCase())) {
      variants.push(stemTrim.slice(0, -suffix.length).trim())
    }
  }
  const out: string[] = []
  const seen = new Set<string>()
  for (const v of variants) {
    if (v && !seen.has(v)) {
      seen.add(v)
      out.push(v)
    }
  }
  return out
}

/** Guess which save team a logo file belongs to (filename without extension). */
export function suggestTeamForLogoFilename(filename: string, teams: string[]): string {
  const stem = filename.replace(/\.[^.]+$/i, '').trim()
  if (!stem || teams.length === 0) return ''
  const byNorm = new Map<string, string>()
  for (const t of teams) {
    const n = normalizeNameKey(t)
    if (n) byNorm.set(n, t)
  }
  for (const v of stemVariants(stem)) {
    const kn = normalizeNameKey(v)
    if (kn && byNorm.has(kn)) return byNorm.get(kn)!
  }
  return ''
}
