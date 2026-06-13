import type { PregamePreviewPlayer } from './pregamePreviewData'
import { themeLabelForGame } from './homeGameThemes'
import { aggregateTeamGameStats } from './scoutingReportEngine'

type TeamAgg = ReturnType<typeof aggregateTeamGameStats>

export type PressBoxQuoteInput = {
  state: any
  week: number
  home: string
  away: string
  gameType: string
  gameIndex: number
  homeDisplay: string
  awayDisplay: string
  venue: string
  homePlayers: PregamePreviewPlayer[]
  awayPlayers: PregamePreviewPlayer[]
  homeAgg: TeamAgg
  awayAgg: TeamAgg
  homeStandings: Record<string, unknown>
  awayStandings: Record<string, unknown>
}

type Ctx = {
  week: number
  year: number
  venue: string
  gameType: string
  home: string
  away: string
  homeDisplay: string
  awayDisplay: string
  homeRec: string
  awayRec: string
  homeW: number
  homeL: number
  awayW: number
  awayL: number
  homePpg: number
  awayPpg: number
  homePpgDef: number
  awayPpgDef: number
  homePrestige: number
  awayPrestige: number
  homeRegion: string
  awayRegion: string
  classification: string
  homeStar: PregamePreviewPlayer | null
  awayStar: PregamePreviewPlayer | null
  homeTheme: string | null
  isRival: boolean
  isRegion: boolean
  isGotw: boolean
  bothWinning: boolean
  shootout: boolean
  mismatch: boolean
  homeHot: boolean
  awayHot: boolean
  desperation: boolean
  homeRushYpg: number
  awayRushYpg: number
  homePassYpg: number
  awayPassYpg: number
  homeRunHeavy: boolean
  awayRunHeavy: boolean
}

const REPORTERS = [
  { name: 'Jake Mercer', title: 'Staff Reporter' },
  { name: 'Riley Chen', title: 'Beat Writer' },
  { name: 'Marcus Hale', title: 'State Desk' },
  { name: 'Dana Brooks', title: 'Friday Night Columnist' },
  { name: 'Terrell Shaw', title: 'Sideline Insider' },
  { name: 'Paige Holloway', title: 'Prep Football Editor' },
  { name: 'Chris Delaney', title: 'Regional Correspondent' },
  { name: 'Nina Ortiz', title: 'Varsity Wire' },
]

function hashStr(s: string): number {
  let h = 0
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0
  return Math.abs(h)
}

class SeededRng {
  private state: number

  constructor(seed: number) {
    this.state = seed >>> 0 || 1
  }

  next(): number {
    this.state = (Math.imul(1664525, this.state) + 1013904223) >>> 0
    return this.state
  }

  pick<T>(items: T[]): T {
    if (!items.length) throw new Error('empty pick pool')
    return items[this.next() % items.length]
  }

  shuffle<T>(items: T[]): T[] {
    const out = [...items]
    for (let i = out.length - 1; i > 0; i--) {
      const j = this.next() % (i + 1)
      ;[out[i], out[j]] = [out[j], out[i]]
    }
    return out
  }
}

function findTeam(state: any, teamName: string) {
  return (state?.teams ?? []).find((t: { name?: string }) => t?.name === teamName) ?? null
}

function teamPrestige(team: any): number {
  const p = Number(team?.prestige)
  return Number.isFinite(p) ? p : 5
}

function winStreakEnteringWeek(state: any, teamName: string, week1Based: number): number {
  let streak = 0
  for (let wi = week1Based - 2; wi >= 0; wi--) {
    const weekGames = state?.weeks?.[wi] ?? []
    const weekRes = state?.week_results?.[wi] ?? []
    let wonThisWeek = false
    let played = false
    for (let gi = 0; gi < weekGames.length; gi++) {
      const g = weekGames[gi]
      const r = weekRes[gi]
      if (!g || !r?.played) continue
      const home = String(g.home ?? '')
      const away = String(g.away ?? '')
      if (home !== teamName && away !== teamName) continue
      played = true
      const hs = Number(r.home_score ?? 0)
      const as = Number(r.away_score ?? 0)
      const userHome = home === teamName
      const userScore = userHome ? hs : as
      const oppScore = userHome ? as : hs
      if (userScore >= oppScore) wonThisWeek = true
    }
    if (!played) break
    if (wonThisWeek) streak++
    else break
  }
  return streak
}

function ppgFromStandings(standings: Record<string, unknown>, games: number): { pf: number; pa: number } {
  const g = Math.max(1, games)
  return {
    pf: Number(standings?.points_for ?? 0) / g,
    pa: Number(standings?.points_against ?? 0) / g,
  }
}

function recordFromStandings(standings: Record<string, unknown>): { w: number; l: number } {
  return {
    w: Number(standings?.wins ?? 0),
    l: Number(standings?.losses ?? 0),
  }
}

function buildCtx(input: PressBoxQuoteInput): Ctx {
  const { state, week, home, away, gameType, gameIndex } = input
  const homeTeamObj = findTeam(state, home)
  const awayTeamObj = findTeam(state, away)
  const hr = recordFromStandings(input.homeStandings)
  const ar = recordFromStandings(input.awayStandings)
  const homeGames = Math.max(1, hr.w + hr.l)
  const awayGames = Math.max(1, ar.w + ar.l)
  const homePpg = ppgFromStandings(input.homeStandings, homeGames)
  const awayPpg = ppgFromStandings(input.awayStandings, awayGames)
  const homePrestige = teamPrestige(homeTeamObj)
  const awayPrestige = teamPrestige(awayTeamObj)

  const isRival = /rival/i.test(gameType)
  const isRegion = /region/i.test(gameType)
  const isGotw = /game of the week/i.test(gameType)

  const homeRushYpg = homeGames > 0 ? Number(input.homeAgg.rushYards ?? 0) / homeGames : 0
  const awayRushYpg = awayGames > 0 ? Number(input.awayAgg.rushYards ?? 0) / awayGames : 0
  const homePassYpg = homeGames > 0 ? Number(input.homeAgg.passYards ?? 0) / homeGames : 0
  const awayPassYpg = awayGames > 0 ? Number(input.awayAgg.passYards ?? 0) / awayGames : 0
  const homeRunHeavy = homeRushYpg > homePassYpg * 1.15 && homeRushYpg >= 100
  const awayRunHeavy = awayRushYpg > awayPassYpg * 1.15 && awayRushYpg >= 100

  return {
    week,
    year: Number(state?.current_year ?? new Date().getFullYear()),
    venue: input.venue,
    gameType,
    home,
    away,
    homeDisplay: input.homeDisplay,
    awayDisplay: input.awayDisplay,
    homeRec: `${hr.w}-${hr.l}`,
    awayRec: `${ar.w}-${ar.l}`,
    homeW: hr.w,
    homeL: hr.l,
    awayW: ar.w,
    awayL: ar.l,
    homePpg: homePpg.pf,
    awayPpg: awayPpg.pf,
    homePpgDef: homePpg.pa,
    awayPpgDef: awayPpg.pa,
    homePrestige,
    awayPrestige,
    homeRegion: String(homeTeamObj?.region ?? '').trim() || '—',
    awayRegion: String(awayTeamObj?.region ?? '').trim() || '—',
    classification: String(homeTeamObj?.classification ?? '—'),
    homeStar: input.homePlayers[0]?.name !== '—' ? input.homePlayers[0] : null,
    awayStar: input.awayPlayers[0]?.name !== '—' ? input.awayPlayers[0] : null,
    homeTheme: themeLabelForGame(state, home, week, gameIndex),
    isRival,
    isRegion,
    isGotw,
    bothWinning: hr.w >= 3 && ar.w >= 3,
    shootout: homePpg.pf >= 24 && awayPpg.pf >= 24,
    mismatch: Math.abs(homePrestige - awayPrestige) >= 4 && Math.abs(hr.w - ar.w) >= 2,
    homeHot: winStreakEnteringWeek(state, home, week) >= 3,
    awayHot: winStreakEnteringWeek(state, away, week) >= 3,
    desperation: isRegion && (hr.w >= ar.w ? ar.w <= 2 : hr.w <= 2) && week >= 7,
    homeRushYpg,
    awayRushYpg,
    homePassYpg,
    awayPassYpg,
    homeRunHeavy,
    awayRunHeavy,
  }
}

type Segment = { weight: number; when?: (c: Ctx) => boolean; text: (c: Ctx) => string }

const LEDES: Segment[] = [
  {
    weight: 1,
    text: (c) =>
      `Under the lights at ${c.venue}, Week ${c.week} finally delivers the matchup everyone circled when the schedule dropped: ${c.awayDisplay} busing in to face ${c.homeDisplay}.`,
  },
  {
    weight: 1,
    text: (c) =>
      `Friday night in ${c.year} doesn't get much cleaner than this — ${c.awayDisplay} (${c.awayRec}) crossing into ${c.homeRegion} territory to test ${c.homeDisplay} (${c.homeRec}) on their home turf.`,
  },
  {
    weight: 1,
    text: (c) =>
      `The gates at ${c.venue} open early tonight; ${c.homeDisplay} and ${c.awayDisplay} both know this Week ${c.week} date carries extra weight in the ${c.classification} race.`,
  },
  {
    weight: 1,
    when: (c) => c.week >= 8,
    text: (c) =>
      `Late-season football hits different, and Week ${c.week} is proof — ${c.awayDisplay} needs a road answer against a ${c.homeDisplay} side that has made ${c.venue} a tough out all fall.`,
  },
  {
    weight: 1,
    when: (c) => c.week <= 3,
    text: (c) =>
      `Still early in ${c.year}, but ${c.homeDisplay} and ${c.awayDisplay} aren't waiting to establish who they are; the Week ${c.week} tape will follow both programs for months.`,
  },
]

const STAKES: Segment[] = [
  {
    weight: 2,
    when: (c) => c.isRival,
    text: () =>
      `Rivalry week strips away the polite talk — alumni from both towns will remind you this one is about pride long before it's about playoffs.`,
  },
  {
    weight: 2,
    when: (c) => c.isGotw,
    text: () =>
      `Statewide eyes land here tonight: the Game of the Week label isn't handed out lightly, and both sidelines understand the magnification.`,
  },
  {
    weight: 2,
    when: (c) => c.isRegion,
    text: (c) =>
      `Region standings don't forgive losses in October; whoever walks out of ${c.venue} with a W tightens their grip on the pod that actually matters in ${c.classification}.`,
  },
  {
    weight: 1,
    when: (c) => c.bothWinning,
    text: (c) =>
      `Two teams with winning records rarely meet without something on the line — ${c.homeRec} vs. ${c.awayRec} is the kind of crossroads game coaches warn you about in August.`,
  },
  {
    weight: 1,
    when: (c) => c.homeW === 0 || c.awayW === 0,
    text: (c) =>
      `Somebody's breakthrough arrives tonight: between ${c.homeDisplay} and ${c.awayDisplay}, one program is still searching for the win that flips their whole season narrative.`,
  },
  {
    weight: 1,
    when: (c) => c.desperation,
    text: () =>
      `The math is getting tight in the region race — this isn't a "we'll get them next year" spot for the team that slips up.`,
  },
  {
    weight: 1,
    text: (c) =>
      `On paper it's ${c.homeDisplay} (${c.homeRec}) hosting ${c.awayDisplay} (${c.awayRec}), but paper doesn't account for how both teams have been practicing all week.`,
  },
]

const MATCHUPS: Segment[] = [
  {
    weight: 2,
    when: (c) => c.shootout,
    text: (c) =>
      `Offense has been the story for both sides — ${c.homeDisplay} averaging ${c.homePpg.toFixed(1)} points against ${c.awayDisplay} at ${c.awayPpg.toFixed(1)}. Somebody's defense has to bend the trend or it'll be a track meet.`,
  },
  {
    weight: 2,
    when: (c) => c.homePpgDef <= 14 || c.awayPpgDef <= 14,
    text: (c) =>
      `Defense travels in this league, and at least one of these units has been stingy (${c.homeDisplay} allowing ${c.homePpgDef.toFixed(1)} PPG, ${c.awayDisplay} ${c.awayPpgDef.toFixed(1)}). Points will be earned, not gifted.`,
  },
  {
    weight: 1,
    when: (c) => c.mismatch,
    text: (c) =>
      c.homePrestige >= c.awayPrestige
        ? `${c.homeDisplay} brings the heavier resume into ${c.venue}, but ${c.awayDisplay} has made a habit of ignoring resumes on Friday night.`
        : `${c.awayDisplay} rolls in with momentum and talent on their side; ${c.homeDisplay} will need the crowd to become a legitimate third phase.`,
  },
  {
    weight: 2,
    when: (c) => c.homeHot,
    text: (c) =>
      `${c.homeDisplay} carries a hot streak into tonight — when you're winning at home, the band hits different and the opening kick feels like an event.`,
  },
  {
    weight: 2,
    when: (c) => c.awayHot,
    text: (c) =>
      `${c.awayDisplay} hasn't cooled off lately, and road confidence is a real weapon; ${c.homeDisplay} has to win the first quarter or risk getting dragged into their pace.`,
  },
  {
    weight: 2,
    when: (c) => c.homeRunHeavy && c.awayRunHeavy,
    text: (c) =>
      `Both teams want to run it — ${c.homeDisplay} at ${c.homeRushYpg.toFixed(0)} rush yards per game, ${c.awayDisplay} at ${c.awayRushYpg.toFixed(0)}. The trenches win this one.`,
  },
  {
    weight: 2,
    when: (c) => c.homeRunHeavy !== c.awayRunHeavy && (c.homeRunHeavy || c.awayRunHeavy),
    text: (c) =>
      c.homeRunHeavy
        ? `${c.homeDisplay} wants to grind (${c.homeRushYpg.toFixed(0)} rush YPG); ${c.awayDisplay} has to set the edge and force them into third-and-long.`
        : `${c.awayDisplay} will test the perimeter on the ground (${c.awayRushYpg.toFixed(0)} rush YPG) — ${c.homeDisplay}'s front seven has to win early downs.`,
  },
  {
    weight: 2,
    when: (c) => c.homePassYpg >= 180 && c.awayPassYpg >= 180,
    text: (c) =>
      `The air game is live: ${c.homeDisplay} averaging ${c.homePassYpg.toFixed(0)} pass yards, ${c.awayDisplay} ${c.awayPassYpg.toFixed(0)}. Secondary play and QB timing will decide who flinches first.`,
  },
  {
    weight: 1,
    when: (c) => c.homeTheme != null,
    text: (c) =>
      `Keep an eye on the atmosphere — ${c.homeDisplay} has tagged this as a "${c.homeTheme}" night at ${c.venue}, and those themed Fridays tend to spike energy on both sidelines.`,
  },
  {
    weight: 1,
    text: (c) =>
      `Special teams and field position usually decide tight ${c.classification} games; with ${c.homeDisplay} at home, the hidden yards in punts and returns loom large.`,
  },
  {
    weight: 1,
    text: (c) =>
      `Turnover margin has separated contenders from pretenders all year — whoever protects the football in the red zone at ${c.venue} walks out with the edge.`,
  },
]

const PLAYERS: Segment[] = [
  {
    weight: 2,
    when: (c) => Boolean(c.homeStar && c.awayStar),
    text: (c) =>
      `The chess match up front sets up the stars: ${c.homeStar!.name} (${c.homeStar!.primaryStat}) has to deliver for ${c.homeDisplay}, while ${c.awayStar!.name} (${c.awayStar!.primaryStat}) gives ${c.awayDisplay} their best punch back.`,
  },
  {
    weight: 2,
    when: (c) => Boolean(c.homeStar),
    text: (c) =>
      `${c.homeDisplay} leans on ${c.homeStar!.name} — ${c.homeStar!.positionLine}, ${c.homeStar!.primaryStat} on the season — to set the tone in front of their own student section.`,
  },
  {
    weight: 2,
    when: (c) => Boolean(c.awayStar),
    text: (c) =>
      `For ${c.awayDisplay}, everything runs through ${c.awayStar!.name} (${c.awayStar!.primaryStat}); if ${c.homeDisplay} doesn't account for No. 1 on the scout card, they'll find out quickly.`,
  },
  {
    weight: 1,
    when: (c) => Boolean(c.homeStar && c.awayStar),
    text: (c) =>
      `Coaches won't say it aloud, but the matchup to watch is ${c.homeStar!.name} vs. ${c.awayDisplay}'s plan to slow him — ${c.awayStar!.name} on the other side ensures ${c.homeDisplay} can't sell out.`,
  },
]

const CLOSERS: Segment[] = [
  {
    weight: 1,
    text: () =>
      `Kickoff can't get here fast enough — four quarters, one winner, and a locker room speech somebody will remember all winter.`,
  },
  {
    weight: 1,
    text: (c) =>
      `By 10 o'clock we'll know a lot more about where ${c.homeDisplay} and ${c.awayDisplay} stand — and so will the rest of the ${c.classification} field watching from home.`,
  },
  {
    weight: 1,
    text: () =>
      `Pack the stands, charge the phones, and find a seat early — this is the kind of high school football night people talk about at the diner tomorrow.`,
  },
  {
    weight: 1,
    when: (c) => c.isRival,
    text: () =>
      `Bragging rights don't expire at midnight — whoever wins gets to live with it until they run it back next fall.`,
  },
  {
    weight: 1,
    text: (c) =>
      `Weather, whistles, and a few big plays — that's the recipe. Everything else is noise until the clock hits zero at ${c.venue}.`,
  },
  {
    weight: 1,
    when: (c) => c.week >= 9,
    text: () =>
      `November football separates teams that want it from teams that hope for it — we'll find out which category each sideline belongs to tonight.`,
  },
]

function eligible(pool: Segment[], ctx: Ctx): Segment[] {
  return pool.filter((s) => !s.when || s.when(ctx))
}

function pickWeighted(rng: SeededRng, pool: Segment[]): Segment {
  const total = pool.reduce((sum, s) => sum + s.weight, 0)
  let roll = rng.next() % total
  for (const seg of pool) {
    roll -= seg.weight
    if (roll < 0) return seg
  }
  return pool[pool.length - 1]
}

function assembleQuote(ctx: Ctx, seed: number): string {
  const rng = new SeededRng(seed)
  const parts: string[] = []

  parts.push(pickWeighted(rng, eligible(LEDES, ctx)).text(ctx))

  const stakesPool = eligible(STAKES, ctx)
  if (stakesPool.length) parts.push(pickWeighted(rng, stakesPool).text(ctx))

  const matchupPool = eligible(MATCHUPS, ctx)
  if (matchupPool.length) {
    const picks = rng.shuffle(matchupPool).slice(0, matchupPool.length >= 2 && rng.next() % 2 === 0 ? 2 : 1)
    for (const seg of picks) parts.push(seg.text(ctx))
  }

  const playerPool = eligible(PLAYERS, ctx)
  if (playerPool.length && rng.next() % 100 > 25) {
    parts.push(pickWeighted(rng, playerPool).text(ctx))
  }

  parts.push(pickWeighted(rng, eligible(CLOSERS, ctx)).text(ctx))

  return parts.join(' ')
}

export function buildPressBoxQuote(input: PressBoxQuoteInput): { name: string; title: string; quote: string } {
  const ctx = buildCtx(input)
  const seed = hashStr(`${input.home}-${input.away}-${input.week}-${input.gameIndex}-${input.gameType}`)
  const rep = REPORTERS[seed % REPORTERS.length]
  const quote = assembleQuote(ctx, seed ^ 0x9e3779b9)
  return { name: rep.name, title: rep.title, quote }
}
