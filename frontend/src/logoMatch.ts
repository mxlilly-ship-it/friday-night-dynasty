/** Mirror backend `_normalize_name`: lowercase, alphanumeric only. */
export function normalizeNameKey(s: string): string {
  return String(s || '')
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]/g, '')
}

const LOGO_STEM_SUFFIXES = ['_logo', '-logo', '_LOGO', '-LOGO', ' logo'] as const
const STADIUM_STEM_SUFFIXES = [
  '_stadium',
  '-stadium',
  '_field',
  '-field',
  ' stadium',
  ...LOGO_STEM_SUFFIXES,
] as const

const HELMET_STEM_SUFFIXES = ['_helmet', '-helmet', ' helmet', ...LOGO_STEM_SUFFIXES] as const

const JERSEY_KIND_SUFFIXES: { suffixes: readonly string[]; kind: 'home' | 'away' | 'alternate' }[] = [
  { suffixes: ['_alternate', '-alternate', '_alt', '-alt', ' alternate'], kind: 'alternate' },
  { suffixes: ['_away', '-away', ' away', '_road', '-road'], kind: 'away' },
  { suffixes: ['_home', '-home', ' home', '_jersey', '-jersey', ' jersey'], kind: 'home' },
]

function stemVariants(stem: string, extraSuffixes: readonly string[] = LOGO_STEM_SUFFIXES): string[] {
  const stemTrim = stem.trim()
  if (!stemTrim) return []
  const variants = [stemTrim]
  for (const suffix of extraSuffixes) {
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

function suggestTeamForAssetFilename(
  filename: string,
  teams: string[],
  suffixes: readonly string[],
): string {
  const stem = filename.replace(/\.[^.]+$/i, '').trim()
  if (!stem || teams.length === 0) return ''
  const byNorm = new Map<string, string>()
  for (const t of teams) {
    const n = normalizeNameKey(t)
    if (n) byNorm.set(n, t)
  }
  for (const v of stemVariants(stem, suffixes)) {
    const kn = normalizeNameKey(v)
    if (kn && byNorm.has(kn)) return byNorm.get(kn)!
  }
  return ''
}

/** Guess which save team a logo file belongs to (filename without extension). */
export function suggestTeamForLogoFilename(filename: string, teams: string[]): string {
  return suggestTeamForAssetFilename(filename, teams, LOGO_STEM_SUFFIXES)
}

/** Guess team from stadium/field photo filenames (e.g. Martinsburg_stadium.jpg). */
export function suggestTeamForStadiumFilename(filename: string, teams: string[]): string {
  return suggestTeamForAssetFilename(filename, teams, STADIUM_STEM_SUFFIXES)
}

/** Guess team from helmet filenames (e.g. Martinsburg_helmet.png). */
export function suggestTeamForHelmetFilename(filename: string, teams: string[]): string {
  return suggestTeamForAssetFilename(filename, teams, HELMET_STEM_SUFFIXES)
}

export type JerseyKind = 'home' | 'away' | 'alternate'

/** Guess team + jersey type from filenames (e.g. Martinsburg_away.png). Defaults to home. */
export function suggestTeamJerseyFilename(
  filename: string,
  teams: string[],
): { team: string; kind: JerseyKind } {
  const stem = filename.replace(/\.[^.]+$/i, '').trim()
  if (!stem || teams.length === 0) return { team: '', kind: 'home' }
  const byNorm = new Map<string, string>()
  for (const t of teams) {
    const n = normalizeNameKey(t)
    if (n) byNorm.set(n, t)
  }
  for (const { suffixes, kind } of JERSEY_KIND_SUFFIXES) {
    for (const suffix of suffixes) {
      if (stem.length > suffix.length && stem.toLowerCase().endsWith(suffix.toLowerCase())) {
        const teamStem = stem.slice(0, -suffix.length).trim()
        for (const v of stemVariants(teamStem, LOGO_STEM_SUFFIXES)) {
          const kn = normalizeNameKey(v)
          if (kn && byNorm.has(kn)) return { team: byNorm.get(kn)!, kind }
        }
      }
    }
  }
  const team = suggestTeamForLogoFilename(filename, teams)
  return { team, kind: 'home' }
}
