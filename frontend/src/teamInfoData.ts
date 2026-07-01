import {
  buildStateChampionshipYearsForTeam,
  buildTeamProgramTotalsFromLeagueHistory,
  mergeInProgressTeamProgramTotals,
  type TeamProgramTotalsDisplay,
} from './coachHistory'
import { teamStadiumName } from './inSeasonDashboardData'
import { formatTeamPoints, formatTeamPointsDelta } from './prestigeUtils'

export type TeamInfoPersonnel = {
  role: 'Captain' | 'Vice Capt.' | 'Key Player'
  name: string
  positionYear: string
}

export type TeamInfoTrophyTier = 'champ' | 'conf' | 'div' | 'playoff'

export type TeamInfoTrophy = {
  tier: TeamInfoTrophyTier
  icon: string
  title: string
  years: string
  count: number
}

export type TeamInfoGradeCard = {
  icon: string
  label: string
  letter: string
  letterClass: 'a' | 'b' | 'c'
  score: number
  maxScore: number
}

export type TeamInfoUniformSlot = {
  id: string
  label: string
  placeholderLabel: string
}

export type TeamInfoRankingPoint = {
  year: number
  rank: number
}

export type TeamInfoNextGame = {
  homeTeam: string
  awayTeam: string
  metaLine: string
  location: string
}

export type TeamInfoRecordRank = {
  record: string
  stateRank: number | null
  classRank: number | null
  classification: string
}

export type TeamInfoRatings = {
  overall: number
  offense: number
  defense: number
  run: number
  pass: number
}

export type TeamInfoData = {
  teamName: string
  nickname: string
  subline: string
  record: string
  stateRankDisplay: string
  classRankDisplay: string
  headCoach: string
  classification: string
  region: string
  rivals: string
  programRecord: string
  playoffAppearances: number
  regionalTitles: number
  stateTitlesDisplay: string
  prestige: string
  prestigeDetail: string
  communityType: string
  enrollment: string
  grades: TeamInfoGradeCard[]
  stadiumName: string
  stadiumCapacity: string
  stadiumSurface: string
  stadiumCondition: string
  stadiumConditionClass: 'good' | ''
  nextGame: TeamInfoNextGame | null
  keyPersonnel: TeamInfoPersonnel[]
  trophies: TeamInfoTrophy[]
  totalHonours: number
  rankingHistory: TeamInfoRankingPoint[]
  ratings: TeamInfoRatings | null
}

function safeStr(v: unknown): string {
  if (v == null) return '—'
  const s = String(v).trim()
  return s || '—'
}

function titleCaseCommunity(raw: string): string {
  if (!raw || raw === '—') return '—'
  return raw
    .split(/[\s_-]+/)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
    .join(' ')
}

function gradeFromScore(score: number, max = 10): TeamInfoGradeCard['letterClass'] {
  const pct = max > 0 ? score / max : 0
  if (pct >= 0.85) return 'a'
  if (pct >= 0.65) return 'b'
  return 'c'
}

function letterFromScore(score: number, max = 10): string {
  const cls = gradeFromScore(score, max)
  if (cls === 'a') return 'A'
  if (cls === 'b') return 'B'
  return score >= max * 0.45 ? 'C' : 'D'
}

function facilitiesConditionLabel(grade: number): { label: string; cls: 'good' | '' } {
  if (grade >= 9) return { label: 'Excellent', cls: 'good' }
  if (grade >= 7) return { label: 'Good', cls: 'good' }
  if (grade >= 5) return { label: 'Average', cls: '' }
  if (grade >= 3) return { label: 'Fair', cls: '' }
  return { label: 'Poor', cls: '' }
}

function estimateCapacity(enrollment: number | null | undefined): string {
  const e = Number(enrollment ?? 0)
  if (!Number.isFinite(e) || e <= 0) return '—'
  const cap = Math.round(Math.min(12000, Math.max(1200, e * 5.5)))
  return cap.toLocaleString()
}

function formatPlayerYear(year: unknown): string {
  const n = Number(year)
  if (Number.isNaN(n)) return '—'
  if (n === 9 || n === 1) return 'FR'
  if (n === 10 || n === 2) return 'SO'
  if (n === 11 || n === 3) return 'JR'
  if (n === 12 || n === 4) return 'SR'
  return String(year)
}

function playerOverall(p: Record<string, unknown>): number {
  const keys = [
    'speed',
    'agility',
    'acceleration',
    'strength',
    'football_iq',
    'coachability',
    'throw_accuracy',
    'catching',
    'run_blocking',
    'pass_blocking',
    'tackling',
    'coverage',
  ]
  const vals = keys.map((k) => Number(p?.[k] ?? 50))
  return vals.reduce((a, b) => a + b, 0) / vals.length
}

function isSenior(p: Record<string, unknown>): boolean {
  const y = Number(p?.year)
  return y === 12 || y === 4
}

export function buildKeyPersonnelFromRoster(roster: unknown): TeamInfoPersonnel[] {
  const list = Array.isArray(roster) ? roster.filter((p) => p && typeof p === 'object') : []
  if (!list.length) {
    return [
      { role: 'Captain', name: '—', positionYear: '—' },
      { role: 'Vice Capt.', name: '—', positionYear: '—' },
      { role: 'Key Player', name: '—', positionYear: '—' },
    ]
  }
  const sorted = [...list].sort(
    (a, b) => playerOverall(b as Record<string, unknown>) - playerOverall(a as Record<string, unknown>),
  )
  const seniors = sorted.filter((p) => isSenior(p as Record<string, unknown>))
  const captain = seniors[0] ?? sorted[0]
  const vice = seniors[1] ?? sorted[1] ?? sorted[0]
  const key = sorted.find((p) => p !== captain && p !== vice) ?? sorted[2] ?? sorted[0]

  const toRow = (p: unknown, role: TeamInfoPersonnel['role']): TeamInfoPersonnel => {
    const row = p as Record<string, unknown>
    const pos = safeStr(row.position ?? row.pos ?? '—')
    const yr = formatPlayerYear(row.year)
    return {
      role,
      name: safeStr(row.name),
      positionYear: `${pos} · ${yr}`,
    }
  }

  return [toRow(captain, 'Captain'), toRow(vice, 'Vice Capt.'), toRow(key, 'Key Player')]
}

function teamClassificationMap(state: any): Map<string, string> {
  const m = new Map<string, string>()
  for (const t of state?.teams ?? []) {
    const name = String(t?.name ?? '').trim()
    if (!name) continue
    const c =
      t?.classification != null && String(t.classification).trim() !== ''
        ? String(t.classification).trim()
        : '—'
    m.set(name, c)
  }
  return m
}

function teamRegionMap(state: any): Map<string, string> {
  const m = new Map<string, string>()
  for (const t of state?.teams ?? []) {
    const name = String(t?.name ?? '').trim()
    if (!name) continue
    const r = t?.region != null && String(t.region).trim() !== '' ? String(t.region).trim() : ''
    m.set(name, r)
  }
  return m
}

export function buildRegionalRivals(state: any, teamName: string): string {
  const clsMap = teamClassificationMap(state)
  const regionMap = teamRegionMap(state)
  const classification = clsMap.get(teamName) ?? '—'
  const region = regionMap.get(teamName) ?? ''
  if (!region || classification === '—') return '—'
  const rivals = (state?.teams ?? [])
    .map((t: { name?: string }) => String(t?.name ?? '').trim())
    .filter((name: string) => {
      if (!name || name === teamName) return false
      return (clsMap.get(name) ?? '—') === classification && (regionMap.get(name) ?? '') === region
    })
    .sort((a: string, b: string) => a.localeCompare(b))
  return rivals.length ? rivals.join(' · ') : '—'
}

function parseRivalsFromTeam(team: unknown): string[] {
  if (!team || typeof team !== 'object') return []
  const raw = (team as { rivals?: unknown }).rivals
  if (Array.isArray(raw)) {
    return raw.map((x) => String(x).trim()).filter(Boolean)
  }
  if (typeof raw === 'string') {
    return raw
      .split(/[,·]/)
      .map((s) => s.trim())
      .filter(Boolean)
  }
  return []
}

/** JSON rivals when set; otherwise same-classification/region peers. */
export function buildTeamRivalsDisplay(state: any, teamName: string): string {
  const team = findTeam(state, teamName)
  const fromJson = parseRivalsFromTeam(team)
  if (fromJson.length) return fromJson.join(' · ')
  return buildRegionalRivals(state, teamName)
}

function standingsRankForTeam(standingsList: unknown[], teamName: string): number | null {
  if (!Array.isArray(standingsList)) return null
  const rows = standingsList
    .filter((r) => r && typeof r === 'object')
    .map((r) => {
      const row = r as Record<string, unknown>
      const pf = Number(row.points_for ?? 0)
      const pa = Number(row.points_against ?? 0)
      return {
        team: String(row.team ?? ''),
        wins: Number(row.wins ?? 0),
        diff: pf - pa,
        pf,
      }
    })
  rows.sort((a, b) => {
    if (b.wins !== a.wins) return b.wins - a.wins
    if (b.diff !== a.diff) return b.diff - a.diff
    return b.pf - a.pf
  })
  const tn = teamName.trim().toLowerCase()
  const idx = rows.findIndex((r) => {
    const rt = r.team.trim().toLowerCase()
    return rt === tn || rt.startsWith(tn) || tn.startsWith(rt.split(' ')[0] ?? '')
  })
  return idx >= 0 ? idx + 1 : null
}

export function buildRankingHistoryForTeam(
  leagueHistory: any,
  teamName: string,
  liveRank: number | null,
  currentYear: number,
): TeamInfoRankingPoint[] {
  const points: TeamInfoRankingPoint[] = []
  const seasons = Array.isArray(leagueHistory?.seasons) ? leagueHistory.seasons : []
  for (const ent of seasons) {
    if (!ent || typeof ent !== 'object') continue
    const rawY = (ent as { year?: unknown }).year ?? (ent as { season?: unknown }).season
    const year = Number(rawY)
    if (!Number.isFinite(year)) continue
    const standingsRaw = (ent as { standings?: unknown }).standings
    const rank = standingsRankForTeam(Array.isArray(standingsRaw) ? standingsRaw : [], teamName)
    if (rank != null) points.push({ year, rank })
  }
  if (liveRank != null && Number.isFinite(currentYear)) {
    const last = points[points.length - 1]
    if (!last || last.year !== currentYear) points.push({ year: currentYear, rank: liveRank })
    else last.rank = liveRank
  }
  return points.slice(-8)
}

function buildRegionalChampionshipYears(leagueHistory: any, teamName: string): number[] {
  const years: number[] = []
  const seasons = Array.isArray(leagueHistory?.seasons) ? leagueHistory.seasons : []
  const tn = teamName.trim().toLowerCase()
  for (const ent of seasons) {
    if (!ent || typeof ent !== 'object') continue
    const rc = (ent as { regional_champions?: unknown }).regional_champions
    if (!Array.isArray(rc)) continue
    const won = rc.some((n) => String(n).trim().toLowerCase().startsWith(tn))
    if (!won) continue
    const rawY = (ent as { year?: unknown }).year ?? (ent as { season?: unknown }).season
    const y = Number(rawY)
    if (Number.isFinite(y)) years.push(y)
  }
  return years.sort((a, b) => a - b)
}

export function buildTrophyRows(
  stateChampionshipYears: number[],
  regionalYears: number[],
  playoffAppearances: number,
  currentYear: number,
): TeamInfoTrophy[] {
  const rows: TeamInfoTrophy[] = []
  if (stateChampionshipYears.length) {
    rows.push({
      tier: 'champ',
      icon: '🏆',
      title: 'State Championship',
      years: stateChampionshipYears.join(' · '),
      count: stateChampionshipYears.length,
    })
  }
  if (regionalYears.length) {
    rows.push({
      tier: 'conf',
      icon: '🥇',
      title: 'Regional Title',
      years: regionalYears.join(' · '),
      count: regionalYears.length,
    })
  }
  if (playoffAppearances > 0) {
    const span =
      regionalYears.length || stateChampionshipYears.length
        ? `${playoffAppearances} appearances`
        : `${playoffAppearances} appearances · through ${currentYear}`
    rows.push({
      tier: 'playoff',
      icon: '🎖️',
      title: 'Playoff Appearances',
      years: span,
      count: playoffAppearances,
    })
  }
  return rows
}

export function getNextGameForTeam(state: any, teamName: string): TeamInfoNextGame | null {
  const phase = String(state?.season_phase ?? '').toLowerCase()
  if (phase !== 'regular') return null
  const weeks = state?.weeks ?? []
  const results = state?.week_results ?? []
  const startWeek = Math.max(0, Number(state?.current_week ?? 1) - 1)

  for (let wi = startWeek; wi < weeks.length; wi++) {
    const weekGames = weeks[wi] ?? []
    const weekRes = results[wi] ?? []
    for (let gi = 0; gi < weekGames.length; gi++) {
      const g = weekGames[gi]
      if (!g) continue
      const home = String(g.home ?? '')
      const away = String(g.away ?? '')
      if (home !== teamName && away !== teamName) continue
      const played = Boolean(weekRes[gi]?.played)
      if (played) continue
      const homeTeam = findTeam(state, home)
      const stadium = teamStadiumName(homeTeam) || `${home} Stadium`
      return {
        homeTeam: home,
        awayTeam: away,
        metaLine: `Week ${wi + 1} · Fri · 7:00 PM`,
        location: stadium,
      }
    }
  }
  return null
}

function findTeam(state: any, teamName: string) {
  return (state?.teams ?? []).find((t: { name?: string }) => t?.name === teamName) ?? null
}

export function buildTeamInfoData(args: {
  saveState: any
  leagueHistory: any
  teamName: string
  recordRank: TeamInfoRecordRank
}): TeamInfoData {
  const { saveState, leagueHistory, teamName, recordRank } = args
  const t = findTeam(saveState, teamName)
  const tm = (t ?? {}) as Record<string, unknown>

  const nickname =
    t?.nickname != null && String(t.nickname).trim() !== ''
      ? safeStr(t.nickname)
      : t?.mascot != null && String(t.mascot).trim() !== ''
        ? safeStr(t.mascot)
        : '—'

  const classification = t?.classification != null ? safeStr(t.classification) : '—'
  const region = t?.region != null && String(t.region).trim() !== '' ? safeStr(t.region) : '—'
  const subline =
    nickname !== '—' && classification !== '—' && region !== '—'
      ? `${nickname} · ${classification} ${region}`
      : nickname !== '—'
        ? nickname
        : classification !== '—'
          ? `${classification}${region !== '—' ? ` ${region}` : ''}`
          : teamName

  const persistedRegional = Number(tm.regional_championships ?? 0)
  const hasLeagueHistSeasons =
    Boolean(leagueHistory) &&
    Array.isArray((leagueHistory as { seasons?: unknown }).seasons) &&
    ((leagueHistory as { seasons: unknown[] }).seasons?.length ?? 0) > 0
  const baseFromTeamsRow: TeamProgramTotalsDisplay | null = teamName
    ? {
        program_wins: Number(tm.program_wins ?? 0),
        program_losses: Number(tm.program_losses ?? 0),
        state_championships: Number(tm.championships ?? 0),
        regional_championships: persistedRegional,
        playoff_appearances: Number(tm.playoff_appearances ?? 0),
      }
    : null
  const histTotals = teamName
    ? mergeInProgressTeamProgramTotals(
        hasLeagueHistSeasons
          ? buildTeamProgramTotalsFromLeagueHistory(leagueHistory, teamName, persistedRegional)
          : baseFromTeamsRow!,
        teamName,
        saveState,
      )
    : null

  const programWins = histTotals?.program_wins ?? Number(tm.program_wins ?? 0)
  const programLosses = histTotals?.program_losses ?? Number(tm.program_losses ?? 0)
  const playoffApps = histTotals?.playoff_appearances ?? Number(tm.playoff_appearances ?? 0)
  const regionalTitles = histTotals?.regional_championships ?? persistedRegional

  const stateChampionshipYears = buildStateChampionshipYearsForTeam(leagueHistory, teamName, saveState)
  const regionalYears = buildRegionalChampionshipYears(leagueHistory, teamName)
  const persistedStateTitles = Math.max(
    0,
    Number(histTotals?.state_championships ?? tm.championships ?? 0) || 0,
  )
  const stateTitlesDisplay =
    stateChampionshipYears.length > 0
      ? String(stateChampionshipYears.length)
      : persistedStateTitles > 0
        ? String(persistedStateTitles)
        : 'None'

  const facScore = Number(t?.facilities_grade ?? 0)
  const culScore = Number(t?.culture_grade ?? 0)
  const boostScore = Number(t?.booster_support ?? 0)
  const condition = facilitiesConditionLabel(facScore)

  const teamPoints =
    tm.team_points != null && Number.isFinite(Number(tm.team_points))
      ? formatTeamPoints(Number(tm.team_points))
      : null
  const tpDelta = formatTeamPointsDelta(Number(tm.team_points_last_delta ?? 0))

  const currentYear = Number(saveState?.current_year ?? new Date().getFullYear())
  const trophies = buildTrophyRows(stateChampionshipYears, regionalYears, playoffApps, currentYear)
  const totalHonours = trophies.reduce((sum, tr) => sum + tr.count, 0)

  return {
    teamName: teamName || '—',
    nickname,
    subline,
    record: recordRank.record,
    stateRankDisplay: recordRank.stateRank != null ? `#${recordRank.stateRank}` : '—',
    classRankDisplay:
      recordRank.classRank != null && recordRank.classification !== '—'
        ? `#${recordRank.classRank} (${recordRank.classification})`
        : recordRank.classRank != null
          ? `#${recordRank.classRank}`
          : '—',
    headCoach: t?.coach?.name != null ? safeStr(t.coach.name) : '—',
    classification,
    region,
    rivals: buildTeamRivalsDisplay(saveState, teamName),
    programRecord: `${programWins}-${programLosses}`,
    playoffAppearances: playoffApps,
    regionalTitles,
    stateTitlesDisplay,
    prestige: t?.prestige != null ? String(t.prestige) : '—',
    prestigeDetail: teamPoints != null ? `${teamPoints} TP · last Δ ${tpDelta}` : `last Δ ${tpDelta}`,
    communityType: titleCaseCommunity(safeStr(t?.community_type)),
    enrollment: t?.enrollment != null ? String(t.enrollment) : '—',
    grades: [
      {
        icon: '🏫',
        label: 'Facilities Grade',
        letter: letterFromScore(facScore),
        letterClass: gradeFromScore(facScore),
        score: facScore,
        maxScore: 10,
      },
      {
        icon: '🤝',
        label: 'Culture Grade',
        letter: letterFromScore(culScore),
        letterClass: gradeFromScore(culScore),
        score: culScore,
        maxScore: 10,
      },
      {
        icon: '💵',
        label: 'Booster Support',
        letter: letterFromScore(boostScore),
        letterClass: gradeFromScore(boostScore),
        score: boostScore,
        maxScore: 10,
      },
    ],
    stadiumName: teamStadiumName(t) || '—',
    stadiumCapacity: estimateCapacity(Number(t?.enrollment)),
    stadiumSurface: 'Natural Grass',
    stadiumCondition: condition.label,
    stadiumConditionClass: condition.cls,
    nextGame: getNextGameForTeam(saveState, teamName),
    keyPersonnel: buildKeyPersonnelFromRoster(t?.roster),
    trophies,
    totalHonours,
    rankingHistory: buildRankingHistoryForTeam(
      leagueHistory,
      teamName,
      recordRank.stateRank,
      currentYear,
    ),
    ratings: null,
  }
}

export const DEFAULT_UNIFORM_SLOTS: TeamInfoUniformSlot[] = [
  { id: 'helmet', label: 'Helmet', placeholderLabel: 'Helmet Photo' },
  { id: 'home', label: 'Home', placeholderLabel: 'Home Jersey' },
  { id: 'away', label: 'Away', placeholderLabel: 'Away Jersey' },
  { id: 'alternate', label: 'Alternate', placeholderLabel: 'Alternate Jersey' },
]
