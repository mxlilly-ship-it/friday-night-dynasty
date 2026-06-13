import { isGameOfTheWeek } from './gameOfTheWeek'
import { teamRecordLine, teamStadiumName } from './inSeasonDashboardData'
import { buildPressBoxQuote } from './pregamePressBox'
import { aggregatePlayerSeasonForTeam, aggregateTeamGameStats } from './scoutingReportEngine'

export type PregamePreviewPlayer = {
  initials: string
  name: string
  positionLine: string
  primaryStat: string
  secondaryStat: string
  side: 'home' | 'away'
}

export type PregamePreviewStatRow = {
  label: string
  value: string
  barPct: number
}

export type PregamePreviewUniform = {
  title: string
  swatches: string[]
  teamName: string
  kind: 'helmet' | 'jersey-home' | 'jersey-away'
}

export type PregamePreviewData = {
  week: number
  homeTeam: string
  awayTeam: string
  homeDisplay: string
  awayDisplay: string
  homeInitials: string
  awayInitials: string
  homeRecord: string
  awayRecord: string
  meta: {
    dateLabel: string
    timeLabel: string
    venue: string
    gameType: string
  }
  reporter: {
    name: string
    title: string
    quote: string
  }
  venue: {
    stadiumName: string
    surfaceLine: string
    capacity: string
    showHomeAdvantage: boolean
  }
  homeStats: PregamePreviewStatRow[]
  awayStats: PregamePreviewStatRow[]
  uniforms: PregamePreviewUniform[]
  homePlayers: PregamePreviewPlayer[]
  awayPlayers: PregamePreviewPlayer[]
  marquee: {
    homeName: string
    homeDetail: string
    homeStat: string
    awayName: string
    awayDetail: string
    awayStat: string
  }
  footerKickoff: string
}

function findTeam(state: any, teamName: string) {
  return (state?.teams ?? []).find((t: { name?: string }) => t?.name === teamName) ?? null
}

function teamDisplayName(team: any, fallback: string): string {
  const nick = String(team?.nickname ?? '').trim()
  if (nick) return nick
  return fallback
}

function teamInitials(teamName: string, team: any): string {
  const abbr = String(team?.abbreviation ?? '').trim()
  if (abbr.length >= 2) return abbr.slice(0, 2).toUpperCase()
  const parts = teamName.split(/\s+/).filter(Boolean)
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase()
  return teamName.slice(0, 2).toUpperCase() || '—'
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

function playerByName(team: any, name: string) {
  return (team?.roster ?? []).find((p: { name?: string }) => p?.name === name) ?? null
}

function hashStr(s: string): number {
  let h = 0
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0
  return Math.abs(h)
}

function teamColorSwatches(teamName: string): string[] {
  const h = hashStr(teamName)
  const hue1 = h % 360
  const hue2 = (hue1 + 40 + (h % 80)) % 360
  const hue3 = (hue1 + 180) % 360
  return [`hsl(${hue1}, 55%, 32%)`, `hsl(${hue2}, 45%, 48%)`, `hsl(${hue3}, 30%, 72%)`]
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

function isRegionGame(
  home: string,
  away: string,
  regionMap: Map<string, string>,
  classificationMap: Map<string, string>,
): boolean {
  const hr = regionMap.get(home) ?? ''
  const ar = regionMap.get(away) ?? ''
  if (!hr || !ar || hr !== ar) return false
  const hc = classificationMap.get(home) ?? ''
  const ac = classificationMap.get(away) ?? ''
  if (!hc || !ac || hc === '—' || ac === '—') return false
  return hc === ac
}

function parseRivals(team: unknown): string[] {
  if (!team || typeof team !== 'object') return []
  const raw = (team as { rivals?: unknown }).rivals
  if (Array.isArray(raw)) return raw.map((x) => String(x).trim()).filter(Boolean)
  if (typeof raw === 'string') {
    return raw
      .split(/[,·]/)
      .map((s) => s.trim())
      .filter(Boolean)
  }
  return []
}

function areRivals(state: any, a: string, b: string): boolean {
  const ta = findTeam(state, a)
  const tb = findTeam(state, b)
  return parseRivals(ta).includes(b) || parseRivals(tb).includes(a)
}

function findGameIndex(state: any, week: number, home: string, away: string): number {
  const wi = week - 1
  const weekGames = state?.weeks?.[wi] ?? []
  for (let gi = 0; gi < weekGames.length; gi++) {
    const g = weekGames[gi]
    if (g?.home === home && g?.away === away) return gi
  }
  return 0
}

function barPct(homeVal: number, awayVal: number, side: 'home' | 'away', lowerIsBetter = false): number {
  const h = lowerIsBetter ? Math.max(0.001, 1 / Math.max(homeVal, 0.001)) : Math.max(0, homeVal)
  const a = lowerIsBetter ? Math.max(0.001, 1 / Math.max(awayVal, 0.001)) : Math.max(0, awayVal)
  const total = h + a
  if (total <= 0) return 50
  const pct = side === 'home' ? (h / total) * 100 : (a / total) * 100
  return Math.round(Math.min(92, Math.max(8, pct)))
}

function buildStatRows(
  homeAgg: ReturnType<typeof aggregateTeamGameStats>,
  awayAgg: ReturnType<typeof aggregateTeamGameStats>,
  homeStandings: any,
  awayStandings: any,
): { home: PregamePreviewStatRow[]; away: PregamePreviewStatRow[] } {
  const hg = Math.max(1, homeAgg.games)
  const ag = Math.max(1, awayAgg.games)
  const homePf = Number(homeStandings?.points_for ?? 0)
  const homePa = Number(homeStandings?.points_against ?? 0)
  const awayPf = Number(awayStandings?.points_for ?? 0)
  const awayPa = Number(awayStandings?.points_against ?? 0)

  const specs: {
    label: string
    homeVal: number
    awayVal: number
    fmt: (n: number) => string
    lowerIsBetter?: boolean
  }[] = [
    { label: 'PPG (off)', homeVal: homePf / hg, awayVal: awayPf / ag, fmt: (n) => n.toFixed(1) },
    { label: 'PPG (def)', homeVal: homePa / hg, awayVal: awayPa / ag, fmt: (n) => n.toFixed(1), lowerIsBetter: true },
    {
      label: 'Pass yds/gm',
      homeVal: homeAgg.passYards / hg,
      awayVal: awayAgg.passYards / ag,
      fmt: (n) => String(Math.round(n)),
    },
    {
      label: 'Rush yds/gm',
      homeVal: homeAgg.rushYards / hg,
      awayVal: awayAgg.rushYards / ag,
      fmt: (n) => String(Math.round(n)),
    },
    {
      label: 'Total yds/gm',
      homeVal: (homeAgg.passYards + homeAgg.rushYards) / hg,
      awayVal: (awayAgg.passYards + awayAgg.rushYards) / ag,
      fmt: (n) => String(Math.round(n)),
    },
    {
      label: 'Turnovers',
      homeVal: homeAgg.turnovers,
      awayVal: awayAgg.turnovers,
      fmt: (n) => String(Math.round(n)),
      lowerIsBetter: true,
    },
    {
      label: '3rd down %',
      homeVal: homeAgg.thirdAtt > 0 ? (homeAgg.thirdConv / homeAgg.thirdAtt) * 100 : 0,
      awayVal: awayAgg.thirdAtt > 0 ? (awayAgg.thirdConv / awayAgg.thirdAtt) * 100 : 0,
      fmt: (n) => `${Math.round(n)}%`,
    },
  ]

  const home: PregamePreviewStatRow[] = []
  const away: PregamePreviewStatRow[] = []
  for (const s of specs) {
    home.push({
      label: s.label,
      value: s.fmt(s.homeVal),
      barPct: barPct(s.homeVal, s.awayVal, 'home', s.lowerIsBetter),
    })
    away.push({
      label: s.label,
      value: s.fmt(s.awayVal),
      barPct: barPct(s.homeVal, s.awayVal, 'away', s.lowerIsBetter),
    })
  }
  return { home, away }
}

function playerInitials(name: string): string {
  const parts = name.split(/\s+/).filter(Boolean)
  if (parts.length >= 2) return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
  return name.slice(0, 2).toUpperCase()
}

function positionLine(team: any, playerName: string, posFallback: string): string {
  const p = playerByName(team, playerName)
  const pos = String(p?.position ?? posFallback ?? '—')
  const yr = formatPlayerYear(p?.year)
  return `${pos} · ${yr}`
}

function formatOffensiveStats(row: ReturnType<typeof aggregatePlayerSeasonForTeam>[number]): {
  primary: string
  secondary: string
} {
  const pos = row.pos
  if (pos === 'QB') {
    const tds = row.passTd + row.rushTd
    return {
      primary: `${row.passYds.toLocaleString()} yds`,
      secondary: `${tds} TD · ${row.intT} INT`,
    }
  }
  if (pos === 'RB') {
    const avg = row.att > 0 ? (row.rushYds / row.att).toFixed(1) : '0.0'
    return {
      primary: `${row.rushYds.toLocaleString()} yds`,
      secondary: `${avg} avg · ${row.rushTd} TD`,
    }
  }
  if (pos === 'WR' || pos === 'TE') {
    return {
      primary: `${row.recYds.toLocaleString()} yds`,
      secondary: `${row.rec} rec · ${row.recTd} TD`,
    }
  }
  return {
    primary: `${row.tackles} tkl`,
    secondary: `${row.sacks} sacks · ${row.interceptions} INT`,
  }
}

function computePlayerOverall(p: any): number {
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
  return Math.round(vals.reduce((a, b) => a + b, 0) / vals.length)
}

function playerHasSeasonProduction(row: ReturnType<typeof aggregatePlayerSeasonForTeam>[number]): boolean {
  return (
    row.passYds +
      row.rushYds +
      row.recYds +
      row.tackles +
      row.sacks +
      row.interceptions +
      row.passTd +
      row.rushTd +
      row.recTd >
    0
  )
}

function formatPreviewPlayerStats(
  rosterPlayer: any,
  seasonRow: ReturnType<typeof aggregatePlayerSeasonForTeam>[number] | undefined,
): { primary: string; secondary: string } {
  if (seasonRow && playerHasSeasonProduction(seasonRow)) {
    return formatOffensiveStats(seasonRow)
  }
  const ovr = computePlayerOverall(rosterPlayer)
  const pot = rosterPlayer?.potential
  const potLine = pot != null && pot !== '' ? `Pot ${pot}` : 'No stats yet'
  return {
    primary: `${ovr} OVR`,
    secondary: potLine,
  }
}

function pickKeyPlayers(
  state: any,
  teamName: string,
  side: 'home' | 'away',
): PregamePreviewPlayer[] {
  const team = findTeam(state, teamName)
  const roster = Array.isArray(team?.roster) ? team.roster.filter((p: any) => p && p.name) : []
  const placeholder = (): PregamePreviewPlayer[] => [
    { initials: '—', name: '—', positionLine: '—', primaryStat: '—', secondaryStat: '—', side },
    { initials: '—', name: '—', positionLine: '—', primaryStat: '—', secondaryStat: '—', side },
    { initials: '—', name: '—', positionLine: '—', primaryStat: '—', secondaryStat: '—', side },
  ]

  if (!roster.length) return placeholder()

  const seasonRows = aggregatePlayerSeasonForTeam(state, teamName)
  const seasonByName = new Map(seasonRows.map((r) => [r.name, r]))

  const topThree = [...roster]
    .sort((a, b) => computePlayerOverall(b) - computePlayerOverall(a))
    .slice(0, 3)

  const rows: PregamePreviewPlayer[] = topThree.map((p) => {
    const name = String(p.name)
    const seasonRow = seasonByName.get(name)
    const stats = formatPreviewPlayerStats(p, seasonRow)
    return {
      initials: playerInitials(name),
      name,
      positionLine: positionLine(team, name, String(seasonRow?.pos ?? p?.position ?? '—')),
      primaryStat: stats.primary,
      secondaryStat: stats.secondary,
      side,
    }
  })

  while (rows.length < 3) {
    rows.push(placeholder()[0])
  }
  return rows
}

function buildMarquee(
  state: any,
  homeTeam: string,
  awayTeam: string,
  homePlayers: PregamePreviewPlayer[],
  awayPlayers: PregamePreviewPlayer[],
) {
  const homeTeamObj = findTeam(state, homeTeam)
  const awayTeamObj = findTeam(state, awayTeam)

  const topOff = (teamName: string) => {
    const t = findTeam(state, teamName)
    const roster = (t?.roster ?? []).filter((p: any) => p?.name)
    const off = roster.filter((p: any) =>
      ['QB', 'RB', 'WR', 'TE', 'OL'].includes(String(p?.position ?? '')),
    )
    const pool = off.length ? off : roster
    return [...pool].sort((a, b) => computePlayerOverall(b) - computePlayerOverall(a))[0]
  }
  const topDef = (teamName: string) => {
    const t = findTeam(state, teamName)
    const roster = (t?.roster ?? []).filter((p: any) => p?.name)
    const def = roster.filter((p: any) =>
      ['DL', 'DE', 'DT', 'LB', 'CB', 'S', 'DB'].includes(String(p?.position ?? '')),
    )
    const pool = def.length ? def : roster
    return [...pool].sort((a, b) => computePlayerOverall(b) - computePlayerOverall(a))[0]
  }

  const homeRows = aggregatePlayerSeasonForTeam(state, homeTeam)
  const awayRows = aggregatePlayerSeasonForTeam(state, awayTeam)
  const homeOff = topOff(homeTeam)
  const awayDef = topDef(awayTeam)

  if (homeOff && awayDef) {
    const homeName = String(homeOff.name)
    const awayName = String(awayDef.name)
    const homeSeason = homeRows.find((r) => r.name === homeName)
    const awaySeason = awayRows.find((r) => r.name === awayName)
    const homeStats = formatPreviewPlayerStats(homeOff, homeSeason)
    const awayStats = formatPreviewPlayerStats(awayDef, awaySeason)
    return {
      homeName,
      homeDetail: `${teamDisplayName(homeTeamObj, homeTeam)} ${String(homeOff.position ?? '—')}`,
      homeStat: homeStats.primary,
      awayName,
      awayDetail: `${teamDisplayName(awayTeamObj, awayTeam)} ${String(awayDef.position ?? '—')}`,
      awayStat: awayStats.primary,
    }
  }

  const hp = homePlayers[0]
  const ap = awayPlayers[0]
  return {
    homeName: hp?.name ?? '—',
    homeDetail: hp?.positionLine ?? '—',
    homeStat: hp?.primaryStat ?? '—',
    awayName: ap?.name ?? '—',
    awayDetail: ap?.positionLine ?? '—',
    awayStat: ap?.primaryStat ?? '—',
  }
}

function resolveGameType(
  state: any,
  week: number,
  home: string,
  away: string,
  gameIndex: number,
  regionMap: Map<string, string>,
  clsMap: Map<string, string>,
): string {
  if (isGameOfTheWeek(state, week, gameIndex)) return 'Game of the Week'
  if (areRivals(state, home, away)) return 'Rivalry Game'
  if (isRegionGame(home, away, regionMap, clsMap)) return 'Region Matchup'
  return 'Regular Season'
}

export function buildPregamePreviewData(
  state: any,
  args: { week: number; home: string; away: string },
): PregamePreviewData | null {
  const { week, home, away } = args
  if (!home || !away || home === '—' || away === '—') return null

  const homeTeamObj = findTeam(state, home)
  const awayTeamObj = findTeam(state, away)
  const regionMap = teamRegionMap(state)
  const clsMap = teamClassificationMap(state)
  const gameIndex = findGameIndex(state, week, home, away)
  const gameType = resolveGameType(state, week, home, away, gameIndex, regionMap, clsMap)

  const year = state?.current_year ?? new Date().getFullYear()
  const dateLabel = `Week ${week} · ${year}`
  const timeLabel = '7:00 PM'
  const venueName = teamStadiumName(homeTeamObj) || `${home} Stadium`
  const surface = hashStr(home) % 2 === 0 ? 'Natural grass' : 'Field turf'

  const homeAgg = aggregateTeamGameStats(state, home)
  const awayAgg = aggregateTeamGameStats(state, away)
  const homeStandings = state?.standings?.[home] ?? {}
  const awayStandings = state?.standings?.[away] ?? {}
  const statRows = buildStatRows(homeAgg, awayAgg, homeStandings, awayStandings)

  const homePlayers = pickKeyPlayers(state, home, 'home')
  const awayPlayers = pickKeyPlayers(state, away, 'away')
  const marquee = buildMarquee(state, home, away, homePlayers, awayPlayers)
  const reporter = buildPressBoxQuote({
    state,
    week,
    home,
    away,
    gameType,
    gameIndex,
    homeDisplay: teamDisplayName(homeTeamObj, home),
    awayDisplay: teamDisplayName(awayTeamObj, away),
    venue: venueName,
    homePlayers,
    awayPlayers,
    homeAgg,
    awayAgg,
    homeStandings,
    awayStandings,
  })

  const homeSw = teamColorSwatches(home)
  const awaySw = teamColorSwatches(away)

  return {
    week,
    homeTeam: home,
    awayTeam: away,
    homeDisplay: teamDisplayName(homeTeamObj, home),
    awayDisplay: teamDisplayName(awayTeamObj, away),
    homeInitials: teamInitials(home, homeTeamObj),
    awayInitials: teamInitials(away, awayTeamObj),
    homeRecord: teamRecordLine(state, home),
    awayRecord: teamRecordLine(state, away),
    meta: {
      dateLabel: `Friday · ${dateLabel}`,
      timeLabel,
      venue: venueName,
      gameType,
    },
    reporter,
    venue: {
      stadiumName: venueName,
      surfaceLine: `${surface} · Capacity ${estimateCapacity(Number(homeTeamObj?.enrollment))}`,
      capacity: estimateCapacity(Number(homeTeamObj?.enrollment)),
      showHomeAdvantage: true,
    },
    homeStats: statRows.home,
    awayStats: statRows.away,
    uniforms: [
      {
        title: `${teamDisplayName(homeTeamObj, home)} helmet`,
        swatches: homeSw.slice(0, 2),
        teamName: home,
        kind: 'helmet',
      },
      {
        title: `${teamDisplayName(homeTeamObj, home)} jersey`,
        swatches: homeSw,
        teamName: home,
        kind: 'jersey-home',
      },
      {
        title: `${teamDisplayName(awayTeamObj, away)} helmet`,
        swatches: awaySw.slice(0, 2),
        teamName: away,
        kind: 'helmet',
      },
      {
        title: `${teamDisplayName(awayTeamObj, away)} jersey`,
        swatches: awaySw,
        teamName: away,
        kind: 'jersey-away',
      },
    ],
    homePlayers,
    awayPlayers,
    marquee,
    footerKickoff: `Kickoff ${timeLabel} · ${dateLabel}`,
  }
}
