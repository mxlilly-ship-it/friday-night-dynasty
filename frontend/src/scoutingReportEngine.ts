import type {
  DefensiveScoutingReport,
  OffensiveScoutingReport,
  ScoutingConfidence,
  ScoutingKeyPlayer,
  ScoutingLastWeekBoxScore,
  ScoutingMatchupLine,
  ScoutingOpponentRow,
  ScoutingPace,
  ScoutingReportBundle,
  ScoutingSituationalRow,
} from './scoutingReportTypes'

function findTeam(state: any, teamName: string): any | null {
  for (const t of state?.teams ?? []) {
    if (String(t?.name ?? '') === teamName) return t
  }
  return null
}

function fmtCommunity(raw: unknown): string {
  const s = String(raw ?? 'suburban')
    .replace(/_/g, ' ')
    .trim()
  if (!s) return 'Suburban'
  return s.charAt(0).toUpperCase() + s.slice(1).toLowerCase()
}

function num(p: any, k: string, d = 0): number {
  const v = Number(p?.[k] ?? d)
  return Number.isFinite(v) ? v : d
}

function coachSkill(c: any, k: string): number {
  return Math.max(1, Math.min(10, Math.round(num(c, k, 5))))
}

function hashSeed(s: string): number {
  let h = 2166136261
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i)
    h = Math.imul(h, 16777619)
  }
  return Math.abs(h >>> 0)
}

function pickSeeded<T>(arr: T[], seedKey: string): T {
  return arr[hashSeed(seedKey) % arr.length]
}

/** Aggregate per-game team_stats deltas for one team across regular season week_results. */
function aggregateTeamGameStats(state: any, teamName: string) {
  let games = 0
  let totalPlays = 0
  let rushYards = 0
  let passYards = 0
  let turnovers = 0
  let explosives = 0
  let explosiveRun = 0
  let explosivePass = 0
  let thirdConv = 0
  let thirdAtt = 0
  let fourthConv = 0
  let fourthAtt = 0

  const weeks = state?.weeks ?? []
  const results = state?.week_results ?? []
  for (let wi = 0; wi < weeks.length; wi++) {
    const wk = weeks[wi] ?? []
    const wkRes = results[wi] ?? []
    for (let gi = 0; gi < wk.length; gi++) {
      const g = wk[gi] ?? {}
      const r = wkRes[gi] ?? {}
      if (!r?.played) continue
      const home = String(g?.home ?? '')
      const away = String(g?.away ?? '')
      if (home !== teamName && away !== teamName) continue
      games += 1
      const ts = (r?.team_stats ?? {})[teamName] ?? {}
      totalPlays += Number(ts?.total_plays ?? 0)
      rushYards += Number(ts?.rush_yards ?? 0)
      passYards += Number(ts?.pass_yards ?? 0)
      turnovers += Number(ts?.turnovers ?? 0)
      explosives += Number(ts?.explosives ?? 0)
      explosiveRun += Number(ts?.explosive_run ?? 0)
      explosivePass += Number(ts?.explosive_pass ?? 0)

      const parseDa = (raw: unknown): [number, number] => {
        if (Array.isArray(raw) && raw.length >= 2) {
          return [Number(raw[1] ?? 0), Number(raw[0] ?? 0)]
        }
        const s = String(raw ?? '0/0')
        const m = s.match(/^(\d+)\s*\/\s*(\d+)/)
        if (m) return [Number(m[1]), Number(m[2])]
        return [0, 0]
      }
      const [tc, ta] = parseDa(ts?.third_down)
      thirdConv += tc
      thirdAtt += ta
      const [fc, fa] = parseDa(ts?.fourth_down)
      fourthConv += fc
      fourthAtt += fa
    }
  }

  return {
    games,
    totalPlays,
    rushYards,
    passYards,
    turnovers,
    explosives,
    explosiveRun,
    explosivePass,
    thirdConv,
    thirdAtt,
    fourthConv,
    fourthAtt,
  }
}

function aggregatePlayerSeasonForTeam(state: any, teamName: string) {
  const rows = new Map<
    string,
    {
      name: string
      pos: string
      passYds: number
      rushYds: number
      recYds: number
      rec: number
      att: number
      comp: number
      intT: number
      rushTd: number
      passTd: number
      recTd: number
      sacks: number
      tackles: number
      tfl: number
      interceptions: number
    }
  >()

  const rosterPos = new Map<string, string>()
  const t = findTeam(state, teamName)
  for (const p of t?.roster ?? []) {
    const name = String(p?.name ?? '')
    if (!name) continue
    rosterPos.set(`${teamName}::${name}`, String(p?.position ?? '—'))
  }

  const absorb = (ps: any[]) => {
    for (const s of ps ?? []) {
      const playerName = String(s?.player_name ?? '')
      const tn = String(s?.team_name ?? '')
      if (tn !== teamName || !playerName) continue
      const key = `${teamName}::${playerName}`
      if (!rows.has(key)) {
        rows.set(key, {
          name: playerName,
          pos: rosterPos.get(key) ?? '—',
          passYds: 0,
          rushYds: 0,
          recYds: 0,
          rec: 0,
          att: 0,
          comp: 0,
          intT: 0,
          rushTd: 0,
          passTd: 0,
          recTd: 0,
          sacks: 0,
          tackles: 0,
          tfl: 0,
          interceptions: 0,
        })
      }
      const r = rows.get(key)!
      r.passYds += Number(s?.pass_yds ?? 0)
      r.rushYds += Number(s?.rush_yds ?? 0)
      r.recYds += Number(s?.rec_yds ?? 0)
      r.rec += Number(s?.rec ?? 0)
      r.att += Number(s?.att ?? 0)
      r.comp += Number(s?.comp ?? 0)
      r.intT += Number(s?.int_thrown ?? 0)
      r.rushTd += Number(s?.rush_td ?? 0)
      r.passTd += Number(s?.pass_td ?? 0)
      r.recTd += Number(s?.rec_td ?? 0)
      r.sacks += Number(s?.sacks ?? 0)
      r.tackles += Number(s?.tackles ?? 0)
      r.tfl += Number(s?.tfl ?? 0)
      r.interceptions += Number(s?.interceptions ?? 0)
    }
  }

  for (const wkRes of state?.week_results ?? []) {
    for (const g of wkRes ?? []) {
      if (!g?.played) continue
      absorb(g?.player_stats ?? [])
    }
  }
  for (const s of state?.preseason_scrimmages ?? []) absorb(s?.player_stats ?? [])

  return Array.from(rows.values())
}

function starterName(team: any, pos: string): string | null {
  const order = team?.depth_chart_order?.[pos]
  if (Array.isArray(order) && order.length > 0 && typeof order[0] === 'string') return order[0]
  const roster = team?.roster ?? []
  const hit = roster.find((p: any) => String(p?.position ?? '') === pos)
  return hit ? String(hit.name) : null
}

function playerByName(team: any, name: string): any | null {
  for (const p of team?.roster ?? []) {
    if (String(p?.name ?? '') === name) return p
  }
  return null
}

function confidenceFromGames(g: number): ScoutingConfidence {
  if (g <= 3) return 'early'
  if (g <= 6) return 'building'
  return 'firm'
}

function confidenceLabel(c: ScoutingConfidence): string {
  if (c === 'early') return 'Early season — tendencies are noisy; treat as directional only.'
  if (c === 'building') return 'Mid-season — picture is sharpening week to week.'
  return 'Late sample — tendencies are the most trustworthy.'
}

function sharpness(playcalling: number, schemeTeach: number, games: number): number {
  const base = (playcalling + schemeTeach) / 20
  const g = Math.min(1, games / 10)
  return Math.round((0.35 + 0.45 * base + 0.2 * g) * 100) / 100
}

function paceFromPlays(ppg: number): ScoutingPace {
  if (ppg < 38) return 'slow'
  if (ppg > 52) return 'fast'
  return 'normal'
}

function recentGames(state: any, teamName: string, n = 5) {
  const out: { opp: string; pf: number; pa: number; w: boolean }[] = []
  const weeks = state?.weeks ?? []
  const results = state?.week_results ?? []
  for (let wi = weeks.length - 1; wi >= 0 && out.length < n; wi--) {
    const wk = weeks[wi] ?? []
    const wkRes = results[wi] ?? []
    for (let gi = wk.length - 1; gi >= 0 && out.length < n; gi--) {
      const g = wk[gi] ?? {}
      const r = wkRes[gi] ?? {}
      if (!r?.played) continue
      const home = String(g?.home ?? '')
      const away = String(g?.away ?? '')
      if (home !== teamName && away !== teamName) continue
      const hs = Number(r?.home_score ?? 0)
      const as_ = Number(r?.away_score ?? 0)
      const userHome = home === teamName
      const pf = userHome ? hs : as_
      const pa = userHome ? as_ : hs
      const opp = userHome ? away : home
      out.push({ opp, pf, pa, w: pf > pa })
    }
  }
  return out
}

function describeRecentForm(state: any, teamName: string) {
  const g = recentGames(state, teamName, 8)
  if (g.length === 0) {
    return {
      bigWins: 'No games in the book yet.',
      toughLosses: '—',
      lastGame: 'Awaiting first kickoff.',
    }
  }
  const sortedMargin = [...g].sort((a, b) => b.pf - b.pa - (a.pf - a.pa))
  const best = sortedMargin[0]
  const worst = [...g].sort((a, b) => a.pf - a.pa - (b.pf - b.pa))[0]
  const last = g[0]
  const bigWins =
    best && best.pf - best.pa >= 14
      ? `Statement win vs ${best.opp} (${best.pf}-${best.pa}).`
      : best
        ? `Best recent margin: ${best.opp} (${best.pf}-${best.pa}).`
        : '—'
  const toughLosses =
    worst && worst.pa - worst.pf >= 14
      ? `Rough night vs ${worst.opp} (${worst.pf}-${worst.pa}).`
      : worst && !worst.w
        ? `Closest recent loss: ${worst.opp} (${worst.pf}-${worst.pa}).`
        : 'No blowout losses in this window.'
  const lastGame = `${last.w ? 'W' : 'L'} vs ${last.opp} · ${last.pf}-${last.pa}`
  return { bigWins, toughLosses, lastGame }
}

function buildLastWeekBoxScore(state: any, teamName: string): ScoutingLastWeekBoxScore | null {
  const weeks = state?.weeks ?? []
  const results = state?.week_results ?? []
  for (let wi = weeks.length - 1; wi >= 0; wi--) {
    const wk = weeks[wi] ?? []
    const wkRes = results[wi] ?? []
    for (let gi = wk.length - 1; gi >= 0; gi--) {
      const g = wk[gi] ?? {}
      const r = wkRes[gi] ?? {}
      if (!r?.played) continue
      const home = String(g?.home ?? '')
      const away = String(g?.away ?? '')
      if (home !== teamName && away !== teamName) continue
      const isHome = home === teamName
      const opp = isHome ? away : home
      const hs = Number(r?.home_score ?? 0)
      const as_ = Number(r?.away_score ?? 0)
      const pf = isHome ? hs : as_
      const pa = isHome ? as_ : hs
      const ts = (r?.team_stats ?? {})[teamName] ?? {}
      const notes: string[] = []
      notes.push(`${Number(ts?.total_plays ?? 0)} plays · ${Number(ts?.rush_yards ?? 0)} rush yds · ${Number(ts?.pass_yards ?? 0)} pass yds`)
      notes.push(`${Number(ts?.turnovers ?? 0)} turnovers · ${Number(ts?.explosives ?? 0)} explosives`)
      const pstats = Array.isArray(r?.player_stats) ? r.player_stats : []
      const stars = pstats
        .filter((p: any) => String(p?.team_name ?? '') === teamName)
        .map((p: any) => {
          const name = String(p?.player_name ?? '')
          const passY = Number(p?.pass_yds ?? 0)
          const rushY = Number(p?.rush_yds ?? 0)
          const recY = Number(p?.rec_yds ?? 0)
          const sk = Number(p?.sacks ?? 0)
          const ints = Number(p?.interceptions ?? 0)
          const score = passY + rushY + recY + sk * 35 + ints * 30
          if (!name || score <= 35) return null
          if (passY >= rushY && passY >= recY) return { score, line: `${name}: ${passY} pass yds` }
          if (rushY >= recY) return { score, line: `${name}: ${rushY} rush yds` }
          return { score, line: `${name}: ${recY} rec yds` }
        })
        .filter(Boolean)
        .sort((a: any, b: any) => b.score - a.score)
        .slice(0, 2)
      for (const s of stars) notes.push(String((s as any).line))
      return {
        opponent: opp,
        result: pf > pa ? 'W' : 'L',
        score: `${pf}-${pa}`,
        notes,
      }
    }
  }
  return null
}

function opponentScheduleRows(state: any, teamName: string, limit = 6): ScoutingOpponentRow[] {
  const out: ScoutingOpponentRow[] = []
  const weeks = state?.weeks ?? []
  const results = state?.week_results ?? []
  const standings = state?.standings ?? {}
  for (let wi = weeks.length - 1; wi >= 0 && out.length < limit; wi--) {
    const wk = weeks[wi] ?? []
    const wkRes = results[wi] ?? []
    for (let gi = wk.length - 1; gi >= 0 && out.length < limit; gi--) {
      const g = wk[gi] ?? {}
      const r = wkRes[gi] ?? {}
      if (!r?.played) continue
      const home = String(g?.home ?? '')
      const away = String(g?.away ?? '')
      if (home !== teamName && away !== teamName) continue
      const isHome = home === teamName
      const opponent = isHome ? away : home
      const homeScore = Number(r?.home_score ?? 0)
      const awayScore = Number(r?.away_score ?? 0)
      const pf = isHome ? homeScore : awayScore
      const pa = isHome ? awayScore : homeScore
      const oppStandings = standings?.[opponent] ?? {}
      out.push({
        opponent,
        result: pf >= pa ? 'W' : 'L',
        opponentWins: Number(oppStandings?.wins ?? 0),
        opponentLosses: Number(oppStandings?.losses ?? 0),
      })
    }
  }
  return out
}

function leagueAvgRushShare(state: any): number {
  const teams = (state?.teams ?? []).map((t: any) => String(t?.name ?? '')).filter(Boolean)
  let sum = 0
  let n = 0
  for (const tn of teams) {
    const a = aggregateTeamGameStats(state, tn)
    if (a.games === 0) continue
    const tot = a.rushYards + a.passYards
    if (tot <= 0) continue
    sum += a.rushYards / tot
    n += 1
  }
  return n ? sum / n : 0.5
}

/** ---- Rule banks (extend freely) ---- */
const OFF_STRENGTH_RULES: { test: (ctx: any) => boolean; tag: string }[] = [
  { test: (x) => x.rushShare >= 0.58, tag: 'Strong run identity' },
  { test: (x) => x.passShare >= 0.55, tag: 'Pass-first operation' },
  { test: (x) => x.pypg >= 165, tag: 'Explosive passing volume' },
  { test: (x) => x.rypg >= 165, tag: 'Ground-and-pound production' },
  { test: (x) => x.thirdPct >= 0.44, tag: 'Moves the chains on third down' },
  { test: (x) => x.tdPerGame >= 3.2, tag: 'Finishes drives for touchdowns' },
  { test: (x) => x.explPerGame >= 4.5, tag: 'Chunk-play offense' },
  { test: (x) => x.turnPerGame <= 0.9, tag: 'Protects the football' },
  { test: (x) => x.ppg >= 32, tag: 'High scoring pace' },
  { test: (x) => x.qbYpa >= 8.5, tag: 'Downfield stress on secondaries' },
  { test: (x) => x.rbYpc >= 5.2, tag: 'Breakaway run threat' },
  { test: (x) => x.wr1Ypg >= 85, tag: 'Alpha wideout production' },
  { test: (x) => x.olPassAvg >= 62, tag: 'Sturdy pocket when they set' },
  { test: (x) => x.playcallerTags.includes('Balanced'), tag: 'Balanced call sheet — harder to predict' },
  { test: (x) => x.coachPlaycalling >= 8, tag: 'Sharp situational playcalling' },
  { test: (x) => x.fourthAggro >= 0.55, tag: 'Aggressive on fourth-down decisions' },
  { test: (x) => x.redPassLean >= 0.58, tag: 'Trusts the QB in tight red-zone windows' },
  { test: (x) => x.redRunLean >= 0.58, tag: 'Pounds it in when the field shrinks' },
]

const OFF_WEAK_RULES: { test: (ctx: any) => boolean; tag: string }[] = [
  { test: (x) => x.turnPerGame >= 2.2, tag: 'Turnover-prone stretches' },
  { test: (x) => x.thirdPct <= 0.32, tag: 'Stalls on third down' },
  { test: (x) => x.sacksAllowedPerGame >= 3.2, tag: 'QB lives under pressure' },
  { test: (x) => x.olPassAvg <= 48, tag: 'Pass protection is a concern' },
  { test: (x) => x.olRunAvg <= 48, tag: 'Run blocking lacks push' },
  { test: (x) => x.ppg <= 16, tag: 'Inconsistent finishing / low point totals' },
  { test: (x) => x.passShare >= 0.62 && x.intRate >= 0.045, tag: 'Volume passing with interception risk' },
  { test: (x) => x.rbYpc <= 3.6, tag: 'Limited run crease' },
  { test: (x) => x.qbYpa <= 5.5, tag: 'Check-down heavy — lacks vertical stress' },
  { test: (x) => x.explPerGame <= 2, tag: 'Rare explosives — grind-heavy' },
  { test: (x) => x.playcallerTags.includes('Conservative'), tag: 'Conservative — leaves meat on the bone' },
  { test: (x) => x.fourthAggro <= 0.25 && x.ppg <= 22, tag: 'Field-position offense without dagger mentality' },
  { test: (x) => x.redConfuse, tag: 'Red-zone inefficiency — yards without paydirt' },
]

const DEF_STRENGTH_RULES: { test: (ctx: any) => boolean; tag: string }[] = [
  { test: (x) => x.sacksPerGame >= 3, tag: 'Disruptive pass rush' },
  { test: (x) => x.tflPerGame >= 5, tag: 'Living in the backfield (TFLs)' },
  { test: (x) => x.intPerGame >= 1.1, tag: 'Takeaway creators' },
  { test: (x) => x.papg <= 14, tag: 'Stingy points allowed' },
  { test: (x) => x.yardsAllowedPerGame <= 220, tag: 'Yardage suppression' },
  { test: (x) => x.secondaryAvg >= 58, tag: 'Secondary plays above its shoes' },
  { test: (x) => x.lbCoverageAvg >= 56, tag: 'Linebackers handle space well' },
  { test: (x) => x.dlRunAvg >= 58, tag: 'Front sets the line of scrimmage' },
  { test: (x) => x.defStyle.includes('Pressure'), tag: 'Pressure-first temperament' },
  { test: (x) => x.defStyle.includes('Zone'), tag: 'Zone shell — rally tackling' },
  { test: (x) => x.blitzLabel === 'high', tag: 'Heat packages show up often' },
]

const DEF_WEAK_RULES: { test: (ctx: any) => boolean; tag: string }[] = [
  { test: (x) => x.papg >= 30, tag: 'Bleeds points in bunches' },
  { test: (x) => x.yardsAllowedPerGame >= 340, tag: 'Yards come easy — leaky structure' },
  { test: (x) => x.secondaryAvg <= 46, tag: 'Corner play is volatile' },
  { test: (x) => x.lbCoverageAvg <= 44, tag: 'Linebackers exposed in space' },
  { test: (x) => x.dlRunAvg <= 46, tag: 'Run fits spring leaks' },
  { test: (x) => x.sacksPerGame <= 1.2, tag: 'Rare sacks — limited disruption' },
  { test: (x) => x.intPerGame <= 0.35, tag: 'Rare takeaways' },
  { test: (x) => x.defStyle.includes('Man') && x.secondaryAvg <= 50, tag: 'Man-heavy without lockdown talent' },
  { test: (x) => x.defStyle.includes('Conservative') && x.papg >= 24, tag: 'Soft shell — still giving up scores' },
]

/** Narrative tied to the defensive playbook (coach.defensive_formation) — layered under stat rules. */
const DEF_PLAYBOOK_SCOUT: Record<string, { strengths: string[]; weaknesses: string[] }> = {
  '4-3': {
    strengths: [
      'Nickel/Dime packages keep speed on the field vs spread and vertical stress',
      '6-2 plug-in for short yardage when you want numbers at the line',
    ],
    weaknesses: [
      'Light-box answers can leak vs downhill power if fits are a step late',
      'Wide install tree — young DB rooms pay for disguise busts',
    ],
  },
  '3-4': {
    strengths: [
      '5-2 and odd fronts fit run-heavy weeks and edge control',
      'Nickel/Dime stay available vs 11 and empty',
    ],
    weaknesses: [
      'Spread tempo can stress the second level in space',
      'Pressure looks punish bad angles when OL sorts doubles cleanly',
    ],
  },
  '5-2': {
    strengths: [
      'Edge numbers — offenses are often funneled inside',
      'Built to win gaps vs heavy personnel and double-tights',
    ],
    weaknesses: [
      'Coverage menu is thinner vs spread and quick game',
      'Slot stress when safeties have to fit and still carry verticals',
    ],
  },
  '3-3 Stack': {
    strengths: [
      'Stack + 3-high shells muddy QB reads vs RPO and modern spread',
      'Simulated/creeper families without giving up dime speed on key downs',
    ],
    weaknesses: [
      'Power run can out-number you if alignments drift',
      'High-discipline scheme — one wrong fit becomes an explosive',
    ],
  },
}

function pickTags<T extends { test: (ctx: any) => boolean; tag: string }>(rules: T[], ctx: any, cap: number): string[] {
  const out: string[] = []
  for (const r of rules) {
    try {
      if (r.test(ctx) && !out.includes(r.tag)) out.push(r.tag)
    } catch {
      /* ignore */
    }
    if (out.length >= cap) break
  }
  return out
}

function mergeDefenseScoutLists(defPlaybook: string, ctx: any, cap: number): { strengths: string[]; weaknesses: string[] } {
  const pb = DEF_PLAYBOOK_SCOUT[defPlaybook]
  const strengths: string[] = []
  const weaknesses: string[] = []
  if (pb) {
    for (const t of pb.strengths) {
      if (strengths.length >= 2) break
      strengths.push(t)
    }
    for (const t of pb.weaknesses) {
      if (weaknesses.length >= 2) break
      weaknesses.push(t)
    }
  }
  for (const t of pickTags(DEF_STRENGTH_RULES, { ...ctx, defStyle: ctx.defStyle }, cap)) {
    if (!strengths.includes(t) && strengths.length < cap) strengths.push(t)
  }
  for (const t of pickTags(DEF_WEAK_RULES, { ...ctx, defStyle: ctx.defStyle }, cap)) {
    if (!weaknesses.includes(t) && weaknesses.length < cap) weaknesses.push(t)
  }
  return { strengths, weaknesses }
}

function playCallerTags(ctx: {
  rushShare: number
  passShare: number
  ppg: number
  papg: number
  fourthAggro: number
  coachOffStyle: string
}): string[] {
  const tags: string[] = []
  const os = ctx.coachOffStyle.toLowerCase()
  if (ctx.rushShare >= 0.58) tags.push('Run Heavy')
  else if (ctx.passShare >= 0.58) tags.push('Pass Heavy')
  else tags.push('Balanced')
  if (os.includes('heavy pass') || os.includes('pass')) tags.push('Pass philosophy on the marquee')
  if (os.includes('heavy run') || os.includes('run')) tags.push('Run philosophy on the marquee')
  if (ctx.ppg >= 30 && ctx.fourthAggro >= 0.45) tags.push('Aggressive')
  if (ctx.ppg <= 20 && ctx.fourthAggro <= 0.3) tags.push('Conservative')
  return Array.from(new Set(tags)).slice(0, 5)
}

function blitzFromStyle(defStyle: string): 'low' | 'medium' | 'high' {
  const s = defStyle.toLowerCase()
  if (s.includes('pressure') || s.includes('aggressive')) return 'high'
  if (s.includes('base') || s.includes('conservative')) return 'low'
  return 'medium'
}

function coverageTilt(defStyle: string): string {
  const s = defStyle
  if (/man/i.test(s) && !/zone/i.test(s)) return 'Man-heavy shells — expect tight trail and reroutes.'
  if (/zone/i.test(s) && !/man/i.test(s)) return 'Zone-heavy — eyes on the QB, rally to the flat.'
  if (/man/i.test(s) && /zone/i.test(s)) return 'Mixed man/zone — stress the seams and hi-lo voids.'
  return 'Balanced coverage philosophy — disguise becomes the weapon.'
}

function buildOffenseContext(args: {
  g: ReturnType<typeof aggregateTeamGameStats>
  leagueRushShare: number
  pRows: ReturnType<typeof aggregatePlayerSeasonForTeam>
  standings: any
  teamName: string
  coach: any
  team: any
}) {
  const { g, leagueRushShare, pRows, standings, teamName, coach, team } = args
  const games = Math.max(1, g.games)
  const st = standings?.[teamName] ?? {}
  const pf = Number(st?.points_for ?? 0)
  const pa = Number(st?.points_against ?? 0)
  const gamesRec = Math.max(1, Number(st?.wins ?? 0) + Number(st?.losses ?? 0))
  const ppg = pf / gamesRec
  const papg = pa / gamesRec
  const yds = g.rushYards + g.passYards
  const rushShare = yds > 0 ? g.rushYards / yds : leagueRushShare
  const passShare = 1 - rushShare
  const playsPerGame = g.totalPlays / games
  const thirdPct = g.thirdAtt > 0 ? g.thirdConv / g.thirdAtt : 0.38
  const fourthAggro = g.fourthAtt > 0 ? g.fourthConv / g.fourthAtt : 0.4
  const turnPerGame = g.turnovers / games
  const explPerGame = g.explosives / games
  const rypg = g.rushYards / games
  const pypg = g.passYards / games

  const qb = pRows.find((r) => r.pos === 'QB')
  const rb = pRows.filter((r) => r.pos === 'RB').sort((a, b) => b.rushYds - a.rushYds)[0]
  const wrs = pRows.filter((r) => r.pos === 'WR' || r.pos === 'TE').sort((a, b) => b.recYds - a.recYds)
  const wr1 = wrs[0]
  const qbAtt = qb?.att ?? 0
  const qbYpa = qbAtt > 0 ? (qb?.passYds ?? 0) / qbAtt : 0
  const rbCarries = Math.max(1, Math.round((rb?.rushYds ?? 0) / 5))
  const rbYpc = rb ? rb.rushYds / rbCarries : 0
  const wr1Ypg = wr1 ? wr1.recYds / games : 0
  const intRate = qbAtt > 0 ? (qb?.intT ?? 0) / qbAtt : 0

  const ols = (team?.roster ?? []).filter((p: any) => String(p?.position ?? '') === 'OL')
  const olPassAvg =
    ols.length > 0 ? ols.reduce((s: number, p: any) => s + num(p, 'pass_blocking', 50), 0) / ols.length : 50
  const olRunAvg = ols.length > 0 ? ols.reduce((s: number, p: any) => s + num(p, 'run_blocking', 50), 0) / ols.length : 50

  const tdPerGame =
    pRows.reduce((s, r) => s + r.passTd + r.rushTd + r.recTd, 0) / Math.max(1, games)

  const coachOffStyle = String(coach?.offensive_style ?? 'Balanced')
  const coachPlaycalling = coachSkill(coach, 'playcalling')
  const playcallerTags = playCallerTags({
    rushShare,
    passShare,
    ppg,
    papg,
    fourthAggro,
    coachOffStyle,
  })

  const styleNoise = Math.sin((teamName.length + coachPlaycalling) * 12.9898) * 0.5 + 0.5
  const redPassLean = 0.42 + styleNoise * 0.22
  const redRunLean = 1 - redPassLean
  const redConfuse = tdPerGame < 2.4 && ppg >= 22

  const sacksProxy = Math.max(0, papg * 0.12 + (70 - olPassAvg) * 0.04)

  return {
    games,
    gamesRec,
    ppg,
    papg,
    rushShare,
    passShare,
    playsPerGame,
    thirdPct,
    fourthAggro,
    turnPerGame,
    explPerGame,
    rypg,
    pypg,
    qbYpa,
    rbYpc,
    wr1Ypg,
    intRate,
    olPassAvg,
    olRunAvg,
    tdPerGame,
    coachOffStyle,
    coachPlaycalling,
    playcallerTags,
    redPassLean,
    redRunLean,
    redConfuse,
    sacksAllowedPerGame: sacksProxy,
    qb,
    rb,
    wr1,
    wrs,
    ols,
  }
}

function buildDefenseContext(args: {
  g: ReturnType<typeof aggregateTeamGameStats>
  teamName: string
  state: any
  coach: any
  team: any
  pRows: ReturnType<typeof aggregatePlayerSeasonForTeam>
}) {
  const { g, teamName, state, coach, team, pRows } = args
  const games = Math.max(1, g.games)
  const st = state?.standings?.[teamName] ?? {}
  const pf = Number(st?.points_for ?? 0)
  const pa = Number(st?.points_against ?? 0)
  const gamesRec = Math.max(1, Number(st?.wins ?? 0) + Number(st?.losses ?? 0))
  const papg = pa / gamesRec
  const yardsAllowedPerGame = (g.passYards + g.rushYards) / games

  let oppPassYards = 0
  let oppRushYards = 0
  let oppGames = 0
  const weeks = state?.weeks ?? []
  const results = state?.week_results ?? []
  for (let wi = 0; wi < weeks.length; wi++) {
    const wk = weeks[wi] ?? []
    const wkRes = results[wi] ?? []
    for (let gi = 0; gi < wk.length; gi++) {
      const gr = wk[gi] ?? {}
      const r = wkRes[gi] ?? {}
      if (!r?.played) continue
      const home = String(gr?.home ?? '')
      const away = String(gr?.away ?? '')
      let opp: string | null = null
      if (home === teamName) opp = away
      else if (away === teamName) opp = home
      else continue
      oppGames += 1
      const ts = (r?.team_stats ?? {})[opp] ?? {}
      oppPassYards += Number(ts?.pass_yards ?? 0)
      oppRushYards += Number(ts?.rush_yards ?? 0)
    }
  }
  const oppPassRate = oppPassYards + oppRushYards > 0 ? oppPassYards / (oppPassYards + oppRushYards) : 0.5

  const defRows = pRows.filter((r) => ['DE', 'DT', 'LB', 'CB', 'S'].includes(r.pos))
  const sacksPerGame = defRows.reduce((s, r) => s + r.sacks, 0) / games
  const tflPerGame = defRows.reduce((s, r) => s + r.tfl, 0) / games
  const intPerGame = defRows.reduce((s, r) => s + r.interceptions, 0) / games

  const cbs = (team?.roster ?? []).filter((p: any) => String(p?.position ?? '') === 'CB')
  const saf = (team?.roster ?? []).filter((p: any) => String(p?.position ?? '') === 'S')
  const lbs = (team?.roster ?? []).filter((p: any) => String(p?.position ?? '') === 'LB')
  const dl = (team?.roster ?? []).filter((p: any) => ['DE', 'DT'].includes(String(p?.position ?? '')))

  const avg = (arr: any[], k: string) =>
    arr.length ? arr.reduce((s, p) => s + num(p, k, 50), 0) / arr.length : 50

  const secondaryAvg = (avg(cbs, 'coverage') * Math.max(1, cbs.length) + avg(saf, 'coverage') * Math.max(1, saf.length)) /
    Math.max(1, cbs.length + saf.length)
  const lbCoverageAvg = avg(lbs, 'coverage')
  const dlRunAvg = avg(dl, 'run_defense')

  const defStyle = String(coach?.defensive_style ?? 'Base')
  const blitzLabel = blitzFromStyle(defStyle)
  const defPlaybook = String(coach?.defensive_formation ?? '4-3')

  return {
    games,
    papg,
    yardsAllowedPerGame,
    sacksPerGame,
    tflPerGame,
    intPerGame,
    secondaryAvg,
    lbCoverageAvg,
    dlRunAvg,
    defStyle,
    blitzLabel,
    oppPassRate,
    pf: pf / gamesRec,
    defPlaybook,
  }
}

function offenseKeyPlayers(team: any, pRows: ReturnType<typeof aggregatePlayerSeasonForTeam>): ScoutingKeyPlayer[] {
  const out: ScoutingKeyPlayer[] = []
  const qbN = starterName(team, 'QB')
  const qb = qbN ? playerByName(team, qbN) : null
  if (qbN && qb) {
    const tha = num(qb, 'throw_accuracy', 50)
    const thp = num(qb, 'throw_power', 50)
    const spd = num(qb, 'speed', 50)
    let tag = 'Balanced operator'
    if (tha >= 58 && thp < 52) tag = 'Game manager — accuracy over arm'
    else if (thp >= 58 && spd >= 52) tag = 'Push-the-pocket creator'
    else if (thp >= 58 && spd < 50) tag = 'Deep-shot arm'
    out.push({ role: 'QB', name: qbN, position: 'QB', tag })
  }
  const rbN = starterName(team, 'RB')
  const rb = rbN ? playerByName(team, rbN) : null
  if (rbN && rb) {
    const btk = num(rb, 'break_tackle', 50)
    const tag = btk >= 56 ? 'Workhorse with contact balance' : 'Slashing / one-cut style'
    out.push({ role: 'RB', name: rbN, position: 'RB', tag })
  }
  const wrByRec = [...pRows].filter((r) => r.pos === 'WR').sort((a, b) => b.recYds - a.recYds)[0]
  const wrName = wrByRec?.name ?? starterName(team, 'WR')
  if (wrName) {
    const wp = playerByName(team, wrName)
    const rte = num(wp, 'route_running', 50)
    const spd = num(wp, 'speed', 50)
    const tag = rte >= 56 && spd >= 56 ? 'Separator / deep threat' : rte >= 54 ? 'Crafty route runner' : 'Possession target'
    out.push({ role: 'WR1', name: wrName, position: 'WR', tag })
  }
  const ols = (team?.roster ?? []).filter((p: any) => String(p?.position ?? '') === 'OL')
  if (ols.length) {
    const weakest = [...ols].sort((a, b) => num(a, 'pass_blocking', 50) + num(a, 'run_blocking', 50) - (num(b, 'pass_blocking', 50) + num(b, 'run_blocking', 50)))[0]
    const nm = String(weakest?.name ?? 'OL')
    out.push({
      role: 'Weakest OL',
      name: nm,
      position: 'OL',
      tag: 'Pressure tends to find this edge first',
    })
  }
  return out.slice(0, 5)
}

function offenseMatchups(team: any, ctx: any): { attack: ScoutingMatchupLine[]; stop: ScoutingMatchupLine[] } {
  const attack: ScoutingMatchupLine[] = []
  const stop: ScoutingMatchupLine[] = []
  const ols = (team?.roster ?? []).filter((p: any) => String(p?.position ?? '') === 'OL')
  if (ols.length) {
    const w = [...ols].sort((a, b) => num(a, 'pass_blocking', 50) - num(b, 'pass_blocking', 50))[0]
    attack.push({
      arrow: 'attack',
      position: 'OL',
      player: String(w?.name ?? ''),
      reason: `Lowest pass-pro anchor (${num(w, 'pass_blocking', 0)} PBK) — isolate speed rush.`,
    })
  }
  const qbN = starterName(team, 'QB')
  const qb = qbN ? playerByName(team, qbN) : null
  if (qb && (num(qb, 'composure', 50) <= 46 || ctx.sacksAllowedPerGame >= 2.8)) {
    attack.push({
      arrow: 'attack',
      position: 'QB',
      player: qbN!,
      reason: 'Comfort drops when bodies collapse — crowd the pocket early.',
    })
  }
  const wrs = (team?.roster ?? []).filter((p: any) => String(p?.position ?? '') === 'WR')
  if (wrs.length >= 2) {
    const sorted = [...wrs].sort((a, b) => num(a, 'route_running', 50) - num(b, 'route_running', 50))
    const w = sorted[0]
    attack.push({
      arrow: 'attack',
      position: 'WR',
      player: String(w?.name ?? ''),
      reason: 'Route detail lags the top of the room — bracket help possible.',
    })
  }
  const rbN = starterName(team, 'RB')
  const rb = rbN ? playerByName(team, rbN) : null
  if (rb && num(rb, 'ball_security', 55) <= 48) {
    attack.push({
      arrow: 'attack',
      position: 'RB',
      player: rbN!,
      reason: 'Strip chances rise in traffic — gang tackle and punch at the ball.',
    })
  }

  if (rb && num(rb, 'break_tackle', 50) >= 56) {
    stop.push({
      arrow: 'stop',
      position: 'RB',
      player: rbN!,
      reason: 'Finishes through contact — leverage and spill players to help.',
    })
  }
  const topWr = [...wrs].sort((a, b) => num(b, 'speed', 50) + num(b, 'catching', 50) - (num(a, 'speed', 50) + num(a, 'catching', 50)))[0]
  if (topWr) {
    stop.push({
      arrow: 'stop',
      position: 'WR',
      player: String(topWr.name),
      reason: 'Top vertical/catch threat — respect double clouds.',
    })
  }
  if (ols.length) {
    const best = [...ols].sort((a, b) => num(b, 'run_blocking', 50) - num(a, 'run_blocking', 50))[0]
    stop.push({
      arrow: 'stop',
      position: 'OL',
      player: String(best?.name ?? ''),
      reason: 'Anchor side in the run game — spill to weaker tackle first.',
    })
  }
  if (qb && num(qb, 'throw_accuracy', 50) >= 58 && num(qb, 'decisions', 50) >= 56) {
    stop.push({
      arrow: 'stop',
      position: 'QB',
      player: qbN!,
      reason: 'Keeps chains on schedule — disguise coverage post-snap.',
    })
  }
  return {
    attack: attack.slice(0, 4),
    stop: stop.slice(0, 4),
  }
}

function defenseMatchups(team: any, ctx: any): { attack: ScoutingMatchupLine[]; avoid: ScoutingMatchupLine[] } {
  const attack: ScoutingMatchupLine[] = []
  const avoid: ScoutingMatchupLine[] = []
  const cbs = (team?.roster ?? []).filter((p: any) => String(p?.position ?? '') === 'CB')
  if (cbs.length) {
    const w = [...cbs].sort((a, b) => num(a, 'coverage', 50) - num(b, 'coverage', 50))[0]
    attack.push({
      arrow: 'attack',
      position: 'CB',
      player: String(w?.name ?? ''),
      reason: `Lowest coverage grade in room — isolate with choice routes.`,
    })
  }
  const lbs = (team?.roster ?? []).filter((p: any) => String(p?.position ?? '') === 'LB')
  if (lbs.length) {
    const slow = [...lbs].sort((a, b) => num(a, 'speed', 50) + num(a, 'agility', 50) - (num(b, 'speed', 50) + num(b, 'agility', 50)))[0]
    attack.push({
      arrow: 'attack',
      position: 'LB',
      player: String(slow?.name ?? ''),
      reason: 'Speed in space is a concern — flex TEs and wheel routes.',
    })
  }
  const dl = (team?.roster ?? []).filter((p: any) => ['DE', 'DT'].includes(String(p?.position ?? '')))
  if (dl.length) {
    const w = [...dl].sort((a, b) => num(a, 'run_defense', 50) - num(b, 'run_defense', 50))[0]
    attack.push({
      arrow: 'attack',
      position: String(w?.position ?? 'DL'),
      player: String(w?.name ?? ''),
      reason: 'Run-fit leverage is the soft point — pin/pull and get to the second level.',
    })
  }
  if (ctx.secondaryAvg <= 48) {
    attack.push({
      arrow: 'attack',
      position: 'Secondary',
      player: 'Group',
      reason: 'Numbers say explosive pass windows exist — take calculated shots.',
    })
  }

  const de = dl.filter((p: any) => String(p?.position ?? '') === 'DE')
  const topRusher = [...de].sort((a, b) => num(b, 'pass_rush', 50) - num(a, 'pass_rush', 50))[0]
  if (topRusher && num(topRusher, 'pass_rush', 50) >= 56) {
    avoid.push({
      arrow: 'avoid',
      position: 'DE',
      player: String(topRusher.name),
      reason: 'Elite rush lane — chip, slide protection, quick game.',
    })
  }
  const saf = (team?.roster ?? []).filter((p: any) => String(p?.position ?? '') === 'S')
  const hawk = [...saf].sort((a, b) => num(b, 'coverage', 50) + num(b, 'football_iq', 50) - (num(a, 'coverage', 50) + num(a, 'football_iq', 50)))[0]
  if (hawk && num(hawk, 'coverage', 50) >= 54) {
    avoid.push({
      arrow: 'avoid',
      position: 'S',
      player: String(hawk.name),
      reason: 'Ball-hawk range — protect the post and hold safeties with eyes.',
    })
  }
  const lock = [...cbs].sort((a, b) => num(b, 'coverage', 50) - num(a, 'coverage', 50))[0]
  if (lock && num(lock, 'coverage', 50) >= 58) {
    avoid.push({
      arrow: 'avoid',
      position: 'CB',
      player: String(lock.name),
      reason: 'True shadow ability — pick-on matchups elsewhere.',
    })
  }
  if (ctx.sacksPerGame >= 2.6) {
    avoid.push({
      arrow: 'avoid',
      position: 'Front',
      player: 'Unit',
      reason: 'Heat arrives in waves — max-protect or rhythm throws.',
    })
  }
  return { attack: attack.slice(0, 4), avoid: avoid.slice(0, 4) }
}

function situationalOffense(ctx: any): ScoutingSituationalRow[] {
  const passLong = Math.round(42 + ctx.passShare * 38 + (1 - ctx.thirdPct) * 12)
  const passMed = Math.round(35 + ctx.passShare * 28)
  const passShort = Math.round(28 + (1 - ctx.rushShare) * 22)
  const rzRun = Math.round(ctx.redRunLean * 100)
  const rzPass = 100 - rzRun
  const firstRun = Math.round(ctx.rushShare * 100)
  const inside = Math.round(45 + ctx.rbYpc * 4)
  const outside = 100 - inside
  const shortP = Math.round(32 + (1 - ctx.qbYpa / 12) * 28)
  const medP = Math.round(28 + ctx.passShare * 20)
  const deepP = 100 - shortP - medP
  return [
    { situation: '3rd & Long', label: `Pass-heavy tendency (~${Math.min(92, passLong)}% pass looks)` },
    { situation: '3rd & Medium', label: `Balanced but leans pass (~${passMed}% pass looks)` },
    { situation: '3rd & Short', label: `Short-yardage — ~${100 - passShort}% run / ${passShort}% quick game` },
    { situation: 'Red zone', label: `Tight windows — ~${rzRun}% run-weighted / ${rzPass}% pass-weighted plan` },
    { situation: '1st down', label: `Establishment downs — ~${firstRun}% run-weighted calls` },
    { situation: 'Inside run vs outside', label: `Gap scheme tilt ~${inside}% inside / ${outside}% perimeter` },
    { situation: 'Pass depth', label: `Short ${shortP}% · intermediate ${medP}% · vertical ${Math.max(8, deepP)}%` },
  ]
}

function situationalDefense(blitz: string, ctx: any): ScoutingSituationalRow[] {
  const heat1 = blitz === 'high' ? 'Heavy' : blitz === 'low' ? 'Light' : 'Moderate'
  return [
    { situation: '1st down', label: `${heat1} simulated pressure — set protections early.` },
    { situation: '2nd & long', label: `${blitz === 'high' ? 'Likely sim pressure' : 'Shell + selective heat'}.` },
    { situation: '3rd down', label: `${blitz === 'high' ? 'Aggressive' : 'Calculated'} rush packages — ${Math.round(55 + ctx.sacksPerGame * 8)}% chance of extra rushers on key.` },
    { situation: 'Coverage', label: ctx.coverageTilt },
    { situation: 'Exploit note', label: `Opponents tilted ~${Math.round(ctx.oppPassRate * 100)}% pass by yardage vs this unit.` },
  ]
}

const OFF_SUMMARY_HEAD = [
  'Their staff scripts early downs with clear intent — expect opening-drive identity calls.',
  'The coordinator leans into rhythm; once tempo builds they stack calls quickly.',
  'They call to protect confidence: if the first two series are clean, aggression spikes.',
  'Play-calling is matchup aware — they hunt favorable alignments before taking vertical shots.',
  'This offense is sequencing-first: look for constraint calls right after explosives.',
  'They tend to answer pressure with quick-game and screen relief.',
  'Drive structure is deliberate: first-down tendency often sets their whole series.',
  'The offense is comfortable changing pace mid-drive to steal leverage.',
  'They are stubborn with identity in neutral downs, then flexible in must-have moments.',
  'Their coordinator tends to stay patient unless forced into long-yardage scripts.',
  'Expect call-sheet discipline; they usually make you defend every skill group.',
  'They show situational confidence near midfield and in plus territory.',
]

const DEF_SUMMARY_HEAD = [
  'Defensively they teach leverage first — explosive prevention is the baseline rule.',
  'This unit calls pressure to shape throws, not just chase sacks.',
  'Their coordinator values disguise; post-snap picture often changes late.',
  'They build third-down plans around coverage leverage and simulated rush looks.',
  'The defense plays with clear spacing rules and forces methodical drives.',
  'Pressure timing is a feature here — they trigger heat on key downs.',
  'Expect formational answers; they adjust structure by personnel groups.',
  'They trust structure over hero-ball, especially between the 20s.',
  'Coverage discipline is central to their identity, then pressure follows.',
  'This defense wants to dictate tempo by winning first down.',
  'They are comfortable living in mixed shells to blur QB reads.',
  'The call-sheet is aggressive when offenses become predictable.',
]

function offenseRecommendations(ctx: any, box: ScoutingLastWeekBoxScore | null): string[] {
  const out: string[] = []
  if (ctx.rushShare >= 0.56) out.push('Load early-down boxes and force them into 2nd/3rd-and-long passing scripts.')
  if (ctx.passShare >= 0.56) out.push('Disguise two-high shells pre-snap, spin late, and make the QB hold the ball.')
  if (ctx.fourthAggro >= 0.5) out.push('Have 4th-down calls ready around midfield; they are willing to stay on the field.')
  if (ctx.thirdPct >= 0.42) out.push('Win first down. Their chain-moving profile is strongest when 3rd down stays manageable.')
  if (ctx.turnPerGame <= 1.0) out.push('Do not count on freebies — tackle leverage and hidden-yardage wins matter more this week.')
  if (ctx.sacksAllowedPerGame >= 2.7) out.push('Stress protection with simulated creepers and overload looks from field pressure side.')
  if (ctx.redPassLean >= 0.56) out.push('In red zone, sit route windows and make throws finish on the boundary.')
  if (ctx.redRunLean >= 0.56) out.push('In red zone, tighten interior fits and force bounce/edge runs into pursuit.')
  if (box && box.result === 'L') out.push(`Last week they lost ${box.score} vs ${box.opponent}; script early pressure to test confidence.`)
  if (box && box.result === 'W') out.push(`They are coming off a ${box.score} win vs ${box.opponent}; match their opening energy with field-position discipline.`)
  if (out.length < 5) {
    out.push('Rotate coverage pictures after the snap so their first read does not stay clean.')
    out.push('Make them string together 10+ play drives; avoid giving up cheap explosives.')
  }
  return out.slice(0, 5)
}

function defenseRecommendations(ctx: any, box: ScoutingLastWeekBoxScore | null): string[] {
  const out: string[] = []
  if (ctx.blitzLabel === 'high') out.push('Carry a pressure answer package: quick game, screens, and max-protect shot checks.')
  if (ctx.blitzLabel === 'low') out.push('Stay patient vs lighter pressure — take underneath efficiency and avoid forcing throws.')
  if (ctx.secondaryAvg <= 48) out.push('Isolate weaker corners with bunch/stack releases and matchup motion.')
  if (ctx.lbCoverageAvg <= 46) out.push('Target linebackers in space with backs and TEs on option/wheel concepts.')
  if (ctx.sacksPerGame >= 2.7) out.push('Slide protection to their rush side and chip premier edges in clear pass downs.')
  if (ctx.intPerGame >= 1.0) out.push('Protect the post and seam windows; this group punishes late throws.')
  if (ctx.papg <= 18) out.push('Accept methodical gains and avoid low-probability hero balls early in drives.')
  if (ctx.yardsAllowedPerGame >= 320) out.push('Use tempo and condensed formations to stress communication and run fits.')
  if (box && box.result === 'W') out.push(`They beat ${box.opponent} ${box.score} last week; opening-drive script should prioritize clean operations.`)
  if (box && box.result === 'L') out.push(`After a ${box.score} loss to ${box.opponent}, expect them to open aggressively to reset tone.`)
  if (out.length < 5) {
    out.push('Use motions and shifts to force declarations before the snap.')
    out.push('Stay balanced until they prove they can consistently win one call family.')
  }
  return out.slice(0, 5)
}

function assistantOffenseSummary(teamName: string, ctx: any, strengths: string[], weaknesses: string[], box: ScoutingLastWeekBoxScore | null): string {
  const head = pickSeeded(OFF_SUMMARY_HEAD, `${teamName}:${ctx.games}:${Math.round(ctx.playsPerGame)}:${ctx.coachPlaycalling}`)
  const profile = `${teamName} profiles as ${ctx.playcallerTags.slice(0, 2).join(' / ') || 'balanced'} with ${ctx.pace} pace (~${Math.round(ctx.playsPerGame)} plays).`
  const stress = strengths.length ? `Top stress traits: ${strengths.slice(0, 2).join('; ')}.` : 'No dominant stress trait has separated yet.'
  const leaks = weaknesses.length ? `Attack points: ${weaknesses.slice(0, 2).join('; ')}.` : 'Weaknesses are subtle; win on down-and-distance discipline.'
  const boxLine = box ? `Last week: ${box.result} vs ${box.opponent} (${box.score}).` : ''
  return `${head} ${profile} ${stress} ${leaks} ${boxLine}`.trim()
}

function assistantDefenseSummary(teamName: string, ctx: any, strengths: string[], weaknesses: string[], box: ScoutingLastWeekBoxScore | null): string {
  const head = pickSeeded(DEF_SUMMARY_HEAD, `${teamName}:${ctx.games}:${ctx.blitzLabel}:${ctx.defPlaybook}`)
  const profile = `${teamName} on defense (${ctx.defPlaybook}) shows ${ctx.blitzLabel.toUpperCase()} pressure temperament with ${ctx.defStyle}.`
  const respect = strengths.length ? `Respect: ${strengths.slice(0, 2).join('; ')}.` : 'No single calling card dominates; execution decides this matchup.'
  const attack = weaknesses.length ? `Probe: ${weaknesses.slice(0, 2).join('; ')}.` : 'Attack with patience and make them tackle snap after snap.'
  const boxLine = box ? `Most recent result: ${box.result} vs ${box.opponent} (${box.score}).` : ''
  return `${head} ${profile} ${respect} ${attack} ${boxLine}`.trim()
}

export function buildScoutingReportBundle(state: any, teamName: string): ScoutingReportBundle | null {
  const team = findTeam(state, teamName)
  if (!team) return null
  const coach = team?.coach ?? {}
  const g = aggregateTeamGameStats(state, teamName)
  const pRows = aggregatePlayerSeasonForTeam(state, teamName)
  const leagueRushShare = leagueAvgRushShare(state)
  const ctx = buildOffenseContext({ g, leagueRushShare, pRows, standings: state?.standings ?? {}, teamName, coach, team })
  const strengths = pickTags(OFF_STRENGTH_RULES, ctx, 8)
  const weaknesses = pickTags(OFF_WEAK_RULES, ctx, 8)
  const { attack, stop } = offenseMatchups(team, ctx)
  const pace = paceFromPlays(ctx.playsPerGame)
  const yds = g.rushYards + g.passYards
  const runPct = yds > 0 ? Math.round((g.rushYards / yds) * 100) : Math.round(leagueRushShare * 100)
  const passPct = 100 - runPct
  const recent = describeRecentForm(state, teamName)
  const opponentSchedule = opponentScheduleRows(state, teamName, 6)
  const lastWeekBoxScore = buildLastWeekBoxScore(state, teamName)
  const conf = confidenceFromGames(g.games)
  const sharp = sharpness(coachSkill(coach, 'playcalling'), coachSkill(coach, 'scheme_teach'), g.games)

  const offense: OffensiveScoutingReport = {
    teamName,
    schoolTypeLabel: fmtCommunity(team?.community_type ?? team?.community),
    classification: String(team?.classification ?? '—'),
    confidence: conf,
    confidenceNote: confidenceLabel(conf),
    reportSharpness: sharp,
    identity: {
      playbook: String(coach?.offensive_formation ?? 'Spread'),
      philosophy: String(coach?.offensive_style ?? 'Balanced'),
      offensiveStyle: String(coach?.offensive_style ?? 'Balanced'),
      springOffenseFocus: String(coach?.spring_offense_focus ?? 'run_game'),
    },
    runPass: {
      runPct,
      passPct,
      note:
        yds > 0
          ? 'Yardage mix proxy (run vs pass yards) — correlates with how drives are built.'
          : 'Limited sample — leaning on coach philosophy until yardage separates.',
    },
    pace: { label: pace, playsPerGame: Math.round(ctx.playsPerGame * 10) / 10 },
    playCallerType: ctx.playcallerTags,
    recentForm: recent,
    lastWeekBoxScore,
    gameplanRecommendations: offenseRecommendations({ ...ctx, pace }, lastWeekBoxScore),
    opponentSchedule,
    strengths,
    weaknesses,
    whoToAttack: attack,
    whoToStop: stop,
    keyPlayers: offenseKeyPlayers(team, pRows),
    tendencies: situationalOffense(ctx),
    assistantSummary: assistantOffenseSummary(teamName, { ...ctx, pace, games: g.games }, strengths, weaknesses, lastWeekBoxScore),
  }

  const dctx = buildDefenseContext({ g, teamName, state, coach, team, pRows })
  const { strengths: dStrengths, weaknesses: dWeak } = mergeDefenseScoutLists(
    dctx.defPlaybook,
    { ...dctx, defStyle: dctx.defStyle },
    8,
  )
  const dm = defenseMatchups(team, { ...dctx, coverageTilt: coverageTilt(dctx.defStyle) })
  const defense: DefensiveScoutingReport = {
    teamName,
    schoolTypeLabel: fmtCommunity(team?.community_type ?? team?.community),
    classification: String(team?.classification ?? '—'),
    confidence: conf,
    confidenceNote: confidenceLabel(conf),
    reportSharpness: sharp,
    identity: {
      playbook: String(coach?.defensive_formation ?? '4-3'),
      philosophy: String(coach?.defensive_style ?? 'Base'),
      defensiveStyle: String(coach?.defensive_style ?? 'Base'),
      springDefenseFocus: String(coach?.spring_defense_focus ?? 'pass_defense'),
    },
    blitzFrequency: dctx.blitzLabel,
    coverageTilt: coverageTilt(dctx.defStyle),
    lastWeekBoxScore,
    gameplanRecommendations: defenseRecommendations(dctx, lastWeekBoxScore),
    opponentSchedule,
    strengths: dStrengths,
    weaknesses: dWeak,
    whoToAttack: dm.attack,
    whoToAvoid: dm.avoid,
    pressureByDown: situationalDefense(dctx.blitzLabel, { ...dctx, coverageTilt: coverageTilt(dctx.defStyle) }),
    assistantSummary: assistantDefenseSummary(teamName, dctx, dStrengths, dWeak, lastWeekBoxScore),
  }

  return {
    generatedAt: new Date().toISOString(),
    gamesSampled: g.games,
    offense,
    defense,
  }
}

/**
 * Example bundle shape (one fictional read) — useful for tests / docs.
 * Real output comes from `buildScoutingReportBundle(saveState, teamName)`.
 */
export const EXAMPLE_SCOUTING_BUNDLE: ScoutingReportBundle = {
  generatedAt: '2026-04-23T12:00:00.000Z',
  gamesSampled: 7,
  offense: {
    teamName: 'Example High',
    schoolTypeLabel: 'Blue collar',
    classification: '3A',
    confidence: 'building',
    confidenceNote: confidenceLabel('building'),
    reportSharpness: 0.78,
    identity: {
      playbook: 'Spread',
      philosophy: 'Lean Pass',
      offensiveStyle: 'Lean Pass',
      springOffenseFocus: 'pass',
    },
    runPass: { runPct: 42, passPct: 58, note: 'Yardage mix proxy.' },
    pace: { label: 'fast', playsPerGame: 54.2 },
    playCallerType: ['Pass Heavy', 'Aggressive'],
    recentForm: {
      bigWins: 'Statement win vs North Ridge (38-14).',
      toughLosses: 'Closest recent loss: Central (24-27).',
      lastGame: 'W vs Eastview · 31-21',
    },
    lastWeekBoxScore: {
      opponent: 'Eastview',
      result: 'W',
      score: '31-21',
      notes: ['58 plays · 142 rush yds · 228 pass yds', '1 turnovers · 5 explosives'],
    },
    gameplanRecommendations: ['Win first down and force passing scripts.', 'Spin coverage late to change QB picture.'],
    opponentSchedule: [{ opponent: 'Eastview', result: 'W', opponentWins: 6, opponentLosses: 3 }],
    strengths: ['Explosive passing volume', 'Moves the chains on third down', 'Chunk-play offense'],
    weaknesses: ['QB lives under pressure', 'Red-zone inefficiency — yards without paydirt'],
    whoToAttack: [
      { arrow: 'attack', position: 'OL', player: 'J. Smith', reason: 'Lowest pass-pro anchor — speed rush isolation.' },
    ],
    whoToStop: [{ arrow: 'stop', position: 'WR', player: 'D. Allen', reason: 'Top vertical threat — cloud help.' }],
    keyPlayers: [
      { role: 'QB', name: 'C. Ward', position: 'QB', tag: 'Deep-shot arm' },
      { role: 'RB', name: 'M. Jones', position: 'RB', tag: 'Workhorse with contact balance' },
    ],
    tendencies: [{ situation: '3rd & Long', label: 'Pass-heavy tendency (~74% pass looks)' }],
    assistantSummary: 'Example: lean on quick game until protection proves trustworthy.',
  },
  defense: {
    teamName: 'Example High',
    schoolTypeLabel: 'Blue collar',
    classification: '3A',
    confidence: 'building',
    confidenceNote: confidenceLabel('building'),
    reportSharpness: 0.78,
    identity: {
      playbook: '4-3',
      philosophy: 'Heavy Pressure',
      defensiveStyle: 'Heavy Pressure',
      springDefenseFocus: 'pass_defense',
    },
    blitzFrequency: 'high',
    coverageTilt: 'Mixed man/zone — stress the seams.',
    lastWeekBoxScore: {
      opponent: 'Eastview',
      result: 'W',
      score: '31-21',
      notes: ['58 plays · 142 rush yds · 228 pass yds', '1 turnovers · 5 explosives'],
    },
    gameplanRecommendations: ['Carry pressure answers and chip edges.', 'Use motion to force coverage declarations.'],
    opponentSchedule: [{ opponent: 'Eastview', result: 'W', opponentWins: 6, opponentLosses: 3 }],
    strengths: ['Disruptive pass rush', 'Takeaway creators'],
    weaknesses: ['Corner play is volatile'],
    whoToAttack: [{ arrow: 'attack', position: 'CB', player: 'T. Lee', reason: 'Lowest coverage grade — choice routes.' }],
    whoToAvoid: [{ arrow: 'avoid', position: 'DE', player: 'R. King', reason: 'Elite rush — chip help required.' }],
    pressureByDown: [{ situation: '3rd down', label: 'Aggressive rush packages on key.' }],
    assistantSummary: 'Example: tempo and constraint plays to declare linebackers.',
  },
}
