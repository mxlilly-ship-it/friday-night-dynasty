import type { NewsArticle, NewsArticleType, TickerItemType, TickerPriority } from './newsTypes'
import { clipTicker, getNewsCenter, nextId } from './newsStore'

type PlayerGameLine = {
  player_name?: string
  team_name?: string
  pass_yds?: number
  pass_td?: number
  comp?: number
  att?: number
  rush_yds?: number
  rush_td?: number
  rec?: number
  rec_yds?: number
  rec_td?: number
  tackles?: number
  sacks?: number
  interceptions?: number
}

/** Composite poll rank (matches TeamHomePage.buildRankingsRows intent). */
export function teamRankMap(state: any): Map<string, number> {
  const standings = state?.standings ?? {}
  const teamNames = Object.keys(standings)
  const currentWeek = Number(state?.current_week ?? 1)
  const gamesPlayedFallback = Math.max(0, currentWeek - 1)
  const rows = teamNames.map((teamName) => {
    const s = standings[teamName] ?? {}
    const wins = Number(s?.wins ?? 0)
    const losses = Number(s?.losses ?? 0)
    const pointsFor = Number(s?.points_for ?? 0)
    const pointsAgainst = Number(s?.points_against ?? 0)
    const games = Math.max(1, wins + losses || gamesPlayedFallback || 1)
    const diff = pointsFor - pointsAgainst
    const ppg = pointsFor / games
    return { teamName, wins, losses, pointsFor, pointsAgainst, diff, ppg }
  })
  rows.sort((a, b) => {
    if (b.wins !== a.wins) return b.wins - a.wins
    if (b.diff !== a.diff) return b.diff - a.diff
    return b.pointsFor - a.pointsFor
  })
  const scored = rows.map((r) => ({
    ...r,
    score: r.wins * 100 + r.diff * 2 + r.ppg * 3,
  }))
  scored.sort((a, b) => b.score - a.score)
  const m = new Map<string, number>()
  scored.forEach((r, i) => m.set(r.teamName, i + 1))
  return m
}

function winnerFromScores(home: string, away: string, hs: number, ash: number): string | null {
  if (hs === ash) return null
  return hs > ash ? home : away
}

export function computeWinStreak(state: any, team: string): number {
  const results = state?.week_results ?? []
  const weeks = state?.weeks ?? []
  const outcomes: Array<'W' | 'L' | 'T'> = []
  for (let wi = 0; wi < results.length; wi++) {
    const wr = results[wi] ?? []
    const wk = weeks[wi] ?? []
    for (let gi = 0; gi < wr.length; gi++) {
      if (!wr[gi]?.played) continue
      const h = String(wk[gi]?.home ?? '')
      const a = String(wk[gi]?.away ?? '')
      if (h !== team && a !== team) continue
      const hs = Number(wr[gi]?.home_score ?? 0)
      const av = Number(wr[gi]?.away_score ?? 0)
      if (hs === av) outcomes.push('T')
      else {
        const w = winnerFromScores(h, a, hs, av)
        outcomes.push(w === team ? 'W' : 'L')
      }
    }
  }
  let streak = 0
  for (let i = outcomes.length - 1; i >= 0; i--) {
    if (outcomes[i] === 'W') streak++
    else break
  }
  return streak
}

function statLineFromPlayer(p: PlayerGameLine): string | null {
  const name = String(p.player_name ?? '').trim()
  if (!name) return null
  const py = Number(p.pass_yds ?? 0)
  const ptd = Number(p.pass_td ?? 0)
  const comp = Number(p.comp ?? 0)
  const att = Number(p.att ?? 0)
  if (py > 80 || ptd > 0) {
    const cmp = att > 0 ? `${comp}/${att}` : ''
    const tail = cmp ? `${cmp}, ` : ''
    return `${name}: ${tail}${py} yds${ptd ? `, ${ptd} TD` : ''}`
  }
  const ry = Number(p.rush_yds ?? 0)
  const rtd = Number(p.rush_td ?? 0)
  if (ry > 60 || rtd > 0) {
    return `${name}: ${ry} rush yds${rtd ? `, ${rtd} TD` : ''}`
  }
  const recy = Number(p.rec_yds ?? 0)
  const rec = Number(p.rec ?? 0)
  const recTd = Number(p.rec_td ?? 0)
  if (recy > 50 || rec > 5 || recTd > 0) {
    return `${name}: ${rec} rec, ${recy} yds${recTd ? `, ${recTd} TD` : ''}`
  }
  const tk = Number(p.tackles ?? 0)
  const sk = Number(p.sacks ?? 0)
  const ints = Number(p.interceptions ?? 0)
  if (tk >= 8 || sk >= 2 || ints >= 1) {
    const bits = [`${tk} TKL`]
    if (sk) bits.push(`${sk} SCK`)
    if (ints) bits.push(`${ints} INT`)
    return `${name}: ${bits.join(', ')}`
  }
  return null
}

function pickStandoutPlayer(stats: PlayerGameLine[]): { line: string; name: string } | null {
  let best: { line: string; name: string; score: number } | null = null
  for (const p of stats) {
    const line = statLineFromPlayer(p)
    if (!line) continue
    const py = Number(p.pass_yds ?? 0) + Number(p.pass_td ?? 0) * 40
    const ry = Number(p.rush_yds ?? 0) + Number(p.rush_td ?? 0) * 45
    const rc = Number(p.rec_yds ?? 0) + Number(p.rec_td ?? 0) * 45 + Number(p.rec ?? 0) * 3
    const df = Number(p.tackles ?? 0) * 3 + Number(p.sacks ?? 0) * 18 + Number(p.interceptions ?? 0) * 22
    const score = Math.max(py, ry, rc, df)
    const name = String(p.player_name ?? '')
    if (!best || score > best.score) best = { line, name, score }
  }
  return best ? { line: best.line, name: best.name } : null
}

function priorityForGame(meta: { upset: boolean; bigPlayer: boolean }): TickerPriority {
  if (meta.upset || meta.bigPlayer) return 'high'
  return 'normal'
}

function articlePriority(type: NewsArticleType, upset: boolean): number {
  let p = 50
  if (type === 'recap') p += 10
  if (type === 'player') p += 25
  if (upset) p += 30
  return p
}

function buildRecapArticle(input: {
  home: string
  away: string
  hs: number
  ash: number
  ot: boolean
  weekLabel: string
  ranks: Map<string, number>
  playerStats: PlayerGameLine[]
  leagueWeek: number
  seasonYear: number
  seasonPhase: string
}): { article: NewsArticle; meta: { upset: boolean; bigPlayer: boolean }; standout: { line: string; name: string } | null } {
  const { home, away, hs, ash, ot, weekLabel, ranks, playerStats, leagueWeek, seasonYear, seasonPhase } = input
  const win = winnerFromScores(home, away, hs, ash)
  const loser = win ? (win === home ? away : home) : ''
  const title = win ? `${win} Defeats ${loser} ${hs}-${ash}` : `${home} ${hs}, ${away} ${ash} — Tie`
  const tickerBase =
    win === home
      ? `${home} beats ${away} ${hs}-${ash}`
      : win === away
        ? `${away} beats ${home} ${ash}-${hs}`
        : `${home} ties ${away} ${hs}-${ash}`

  let upset = false
  if (win) {
    const wr = ranks.get(win) ?? 99
    const lr = ranks.get(loser) ?? 99
    upset = lr <= 8 && wr > lr + 4
  }

  const st = pickStandoutPlayer(playerStats)
  const bigPlayer = Boolean(st)

  const summaryParts: string[] = []
  if (win) summaryParts.push(`${win} secured the result in ${weekLabel.toLowerCase()}.`)
  else summaryParts.push('Defense held the line in a rare draw.')
  if (st) summaryParts.push(`${st.name} stood out with a key stat line.`)

  const body: string[] = [
    `Final: ${home} ${hs}, ${away} ${ash}${ot ? ' (overtime)' : ''}.`,
    '',
    win ? `${win} controlled the scoreboard when it mattered most.` : 'Neither side could break the deadlock late.',
    '',
    st ? `Player spotlight: ${st.line}.` : 'Balanced effort across both rosters.',
    '',
    upset && win
      ? `Poll shocker: ${win} entered well behind ${loser} and still found a way.`
      : 'Standings tighten as the season grinds on.',
  ]

  let tickerText = clipTicker(tickerBase, 80)
  if (upset && win) {
    const lr = ranks.get(loser) ?? 0
    tickerText = clipTicker(`UPSET: ${win} defeats #${lr} ${loser}`, 80)
  }

  const article: NewsArticle = {
    id: nextId('art'),
    title: clipTicker(title, 72),
    summary: clipTicker(summaryParts.join(' '), 160),
    content: body.join('\n'),
    type: 'recap',
    teams: [home, away],
    players: st ? [st.name] : [],
    timestamp: Date.now(),
    priority: articlePriority(st ? 'player' : 'recap', upset),
    tickerText,
    breaking: upset,
    newsWeek: leagueWeek,
    seasonYear,
    seasonPhase,
  }

  return { article, meta: { upset, bigPlayer }, standout: st }
}

function flattenBracketResults(state: any): any[] {
  const po = state?.playoffs
  if (!po || typeof po !== 'object') return []
  if (Array.isArray(po.bracket_results)) return [...po.bracket_results]
  const by = po.by_class
  if (!by || typeof by !== 'object') return []
  const out: any[] = []
  for (const v of Object.values(by)) {
    const br = (v as any)?.bracket_results
    if (Array.isArray(br)) out.push(...br)
  }
  return out
}

function playoffSeeds(state: any): Map<string, number> {
  const m = new Map<string, number>()
  const po = state?.playoffs
  if (!po) return m
  const pick = (sub: any) => {
    const seeds = sub?.seeds
    if (!Array.isArray(seeds)) return
    for (const s of seeds) {
      const t = String(s?.team ?? '')
      const sd = Number(s?.seed ?? 0)
      if (t) m.set(t, sd || m.get(t) || 99)
    }
  }
  if (Array.isArray(po)) return m
  if (po.by_class && typeof po.by_class === 'object') {
    for (const sub of Object.values(po.by_class)) pick(sub)
  } else pick(po)
  return m
}

const PLAYOFF_RESULT_TICKER_TEMPLATES = [
  '[ROUND]: [WIN] edges [LOSE]',
  '[ROUND]: [WIN] survives [LOSE]',
  '[ROUND]: [WIN] takes down [LOSE]',
  '[ROUND]: [WIN] knocks out [LOSE]',
  '[ROUND]: [WIN] gets past [LOSE]',
  '[ROUND]: [WIN] wins a thriller over [LOSE]',
  '[ROUND]: [WIN] handles [LOSE]',
  '[ROUND]: [WIN] rallies past [LOSE]',
  '[ROUND]: [WIN] closes out [LOSE]',
  '[ROUND]: [WIN] advances past [LOSE]',
]

const PLAYOFF_RESULT_SUMMARY_TEMPLATES = [
  '[WIN] moves on in the [ROUND] after controlling key moments.',
  '[WIN] survives a tight [ROUND] battle and keeps the run alive.',
  '[WIN] delivers in the [ROUND] and punches the next ticket.',
  '[WIN] finds enough late to win in the [ROUND].',
  '[WIN] takes the [ROUND] matchup and extends the postseason push.',
]

function ingestPlayoffGame(prev: any, next: any, center: ReturnType<typeof getNewsCenter>) {
  const prevR = flattenBracketResults(prev)
  const nextR = flattenBracketResults(next)
  if (nextR.length <= prevR.length) return
  const fresh = nextR.slice(prevR.length)
  const seeds = playoffSeeds(next)
  for (const g of fresh) {
    const home = String(g?.home ?? '')
    const away = String(g?.away ?? '')
    const hs = Number(g?.home_score ?? 0)
    const ash = Number(g?.away_score ?? 0)
    const win = String(g?.winner ?? '')
    const round = String(g?.round ?? 'Playoff')
    if (!home || !away || !win) continue
    const dk = `po:${home}:${away}:${hs}:${ash}:${win}`
    if (!center.tryConsumeKey(dk)) continue
    const sh = seeds.get(home) ?? 0
    const sa = seeds.get(away) ?? 0
    const seedLab = (n: number) => (n > 0 ? String(n) : '?')
    const id = nextId('art')
    const title = `#${seedLab(sh)} ${home} vs #${seedLab(sa)} ${away}: ${win} advances`
    const lose = win === home ? away : home
    const tickerTpl = pickOne(PLAYOFF_RESULT_TICKER_TEMPLATES)
    const tickerText = clipTicker(
      tickerTpl
        .replaceAll('[ROUND]', round)
        .replaceAll('[WIN]', win)
        .replaceAll('[LOSE]', lose),
      80,
    )
    const summaryTpl = pickOne(PLAYOFF_RESULT_SUMMARY_TEMPLATES)
    const summaryText = clipTicker(
      summaryTpl
        .replaceAll('[ROUND]', round)
        .replaceAll('[WIN]', win),
      140,
    )
    const article: NewsArticle = {
      id,
      title: clipTicker(title, 78),
      summary: summaryText,
      content: [`${round} spotlight: ${home} ${hs}, ${away} ${ash}.`, '', `${win} punched the next ticket with timely stops and explosive plays.`].join(
        '\n',
      ),
      type: 'recap',
      teams: [home, away],
      players: [],
      timestamp: Date.now(),
      priority: 85,
      tickerText,
      breaking: true,
      newsWeek: 0,
      seasonPhase: 'playoffs',
      seasonYear: Math.max(1, Number(next?.current_year ?? 1)),
    }
    center.addArticleWithTicker(article, {
      id,
      text: tickerText,
      type: 'score',
      priority: 'high',
      relatedArticleId: id,
      newsWeek: 0,
      seasonPhase: 'playoffs',
      seasonYear: article.seasonYear,
    })
  }
}

function ingestScrimmages(prev: any, next: any, center: ReturnType<typeof getNewsCenter>) {
  const pa = (prev?.preseason_scrimmages ?? []) as any[]
  const na = (next?.preseason_scrimmages ?? []) as any[]
  if (na.length <= pa.length) return
  for (const s of na.slice(pa.length)) {
    const home = String(s?.home ?? '')
    const away = String(s?.away ?? '')
    const hs = Number(s?.home_score ?? 0)
    const ash = Number(s?.away_score ?? 0)
    if (!home || !away) continue
    if (!center.tryConsumeKey(`sc:${home}:${away}:${hs}:${ash}`)) continue
    const win = winnerFromScores(home, away, hs, ash)
    const id = nextId('art')
    const tickerText = clipTicker(
      win ? `PRESEASON: ${win} tops ${win === home ? away : home} ${Math.max(hs, ash)}-${Math.min(hs, ash)}` : `PRESEASON: ${home} ${hs}, ${away} ${ash}`,
      80,
    )
    const article: NewsArticle = {
      id,
      title: clipTicker(`Preseason: ${home} ${hs}, ${away} ${ash}`, 72),
      summary: 'Scrimmage tape is in; coaches will grind the corrections all week.',
      content: [`Scrimmage result: ${home} ${hs}, ${away} ${ash}.`, '', 'Film room takeaways: tempo, tackling, and third downs get the first edits.'].join('\n'),
      type: 'feature',
      teams: [home, away],
      players: [],
      timestamp: Date.now(),
      priority: 40,
      tickerText,
      newsWeek: 0,
      seasonPhase: 'preseason',
      seasonYear: Math.max(1, Number(next?.current_year ?? 1)),
    }
    center.addArticleWithTicker(article, {
      id,
      text: tickerText,
      type: 'score',
      priority: 'normal',
      relatedArticleId: id,
      newsWeek: 0,
      seasonPhase: 'preseason',
      seasonYear: article.seasonYear,
    })
  }
}

function ingestCarousel(prev: any, next: any, center: ReturnType<typeof getNewsCenter>) {
  const pa = (prev?.offseason_coach_carousel_last_events ?? []) as any[]
  const na = (next?.offseason_coach_carousel_last_events ?? []) as any[]
  const prevSet = new Set(pa.map((e) => JSON.stringify(e)))
  for (const e of na) {
    const k = JSON.stringify(e)
    if (prevSet.has(k)) continue
    if (!center.tryConsumeKey(`cc:${k}`)) continue
    const typ = String(e?.type ?? '')
    const team = String(e?.team ?? '')
    const coach = String(e?.coach ?? '')
    const detail = String(e?.detail ?? '')
    const fromSchool = String(e?.from_school ?? '')
    const rendered = renderCarouselCopy(typ, {
      team,
      coach,
      from_school: fromSchool,
      detail,
    })
    let title = rendered.title
    let tickerText = rendered.ticker
    let articleType: NewsArticleType = 'feature'
    let tickType: TickerItemType = 'recruiting'
    if (typ === 'firing') {
      articleType = 'feature'
      tickType = 'recruiting'
    } else if (typ === 'hire') {
      articleType = 'feature'
    } else if (typ === 'promotion') {
      articleType = 'feature'
    } else if (typ === 'retirement') {
      articleType = 'feature'
    } else if (typ === 'resignation') {
      articleType = 'feature'
    }
    const id = nextId('art')
    const article: NewsArticle = {
      id,
      title,
      summary: clipTicker(rendered.summary || detail, 160),
      content: [detail, '', 'Power programs watch the carousel — every hire shifts recruiting leverage for January.'].join('\n'),
      type: articleType,
      teams: team ? [team] : [],
      players: [],
      timestamp: Date.now(),
      priority: 70,
      tickerText,
      breaking: typ === 'firing',
      newsWeek: 0,
      seasonPhase: 'offseason',
      seasonYear: Math.max(1, Number(next?.current_year ?? 1)),
    }
    center.addArticleWithTicker(article, {
      id,
      text: tickerText,
      type: tickType,
      priority: typ === 'firing' ? 'high' : 'normal',
      relatedArticleId: id,
      newsWeek: 0,
      seasonPhase: 'offseason',
      seasonYear: article.seasonYear,
    })
  }
}

function ingestTransfers(prev: any, next: any, center: ReturnType<typeof getNewsCenter>) {
  const pa = (prev?.offseason_transfer_news_events ?? []) as any[]
  const na = (next?.offseason_transfer_news_events ?? []) as any[]
  const prevSet = new Set(pa.map((e) => JSON.stringify(e)))
  for (const e of na) {
    const k = JSON.stringify(e)
    if (prevSet.has(k)) continue
    if (!center.tryConsumeKey(`tr:${k}`)) continue
    const typ = String(e?.type ?? '')
    const player = String(e?.player ?? 'Player')
    const from = String(e?.team ?? '')
    const to = String(e?.to_team ?? '')
    const pos = String(e?.position ?? 'ATH')
    const detail = String(e?.detail ?? `${player} transfer update`)
    const year = Math.max(1, Number(next?.current_year ?? 1))
    const title =
      typ === 'transfer_commit'
        ? clipTicker(`${player} transfers to ${to || 'new school'}`, 72)
        : clipTicker(`${player} enters transfer portal`, 72)
    const tickerText =
      typ === 'transfer_commit'
        ? clipTicker(`TRANSFER: ${player} (${pos}) ${from} -> ${to}`, 80)
        : clipTicker(`PORTAL: ${player} (${pos}) leaves ${from}`, 80)
    const id = nextId('art')
    center.addArticleWithTicker(
      {
        id,
        title,
        summary: clipTicker(detail, 160),
        content: [detail, '', 'Transfer movement can reshape depth charts and offseason plans in a hurry.'].join('\n'),
        type: 'recruiting',
        teams: [from, to].filter(Boolean),
        players: [player],
        timestamp: Date.now(),
        priority: typ === 'transfer_commit' ? 66 : 58,
        tickerText,
        newsWeek: 0,
        seasonPhase: 'offseason',
        seasonYear: year,
      },
      {
        id,
        text: tickerText,
        type: 'recruiting',
        priority: typ === 'transfer_commit' ? 'high' : 'normal',
        relatedArticleId: id,
        newsWeek: 0,
        seasonPhase: 'offseason',
        seasonYear: year,
      },
    )
  }
}

const CAROUSEL_COPY_BANK: Record<string, Array<{ title: string; ticker: string; summary: string }>> = {
  firing: [
    { title: '[COACH] out at [TEAM]', ticker: 'CAROUSEL: [TEAM] parts ways with [COACH]', summary: '[TEAM] opens a high-stakes search after moving on from [COACH].' },
    { title: '[TEAM] makes a coaching change', ticker: 'HOT SEAT: [COACH] dismissed at [TEAM]', summary: 'Pressure finally broke through and [TEAM] made a sideline reset.' },
    { title: 'Reset mode at [TEAM]', ticker: '[TEAM] begins HC hunt after firing [COACH]', summary: '[TEAM] pivots into full search mode with expectations still high.' },
    { title: '[COACH] shown the door by [TEAM]', ticker: 'SHAKEUP: [TEAM] fires [COACH]', summary: '[TEAM] leadership decided a new voice is needed this offseason.' },
    { title: '[TEAM] clears the headset', ticker: 'PROGRAM MOVE: [COACH] exits [TEAM]', summary: 'The carousel spins faster as [TEAM] joins the vacancy list.' },
    { title: 'Major sideline turnover at [TEAM]', ticker: 'OFFSEASON: [TEAM] cuts ties with [COACH]', summary: '[TEAM] bets on a fresh direction after an uneven run.' },
  ],
  hire: [
    { title: '[TEAM] hires [COACH]', ticker: 'HIRED: [COACH] takes over at [TEAM]', summary: '[TEAM] lands its next head coach and starts installing the new plan.' },
    { title: '[COACH] introduced at [TEAM]', ticker: 'CAROUSEL: [TEAM] announces [COACH]', summary: '[COACH] is now tasked with elevating [TEAM] in a packed class race.' },
    { title: '[TEAM] finalizes coaching search', ticker: 'NEW HC: [COACH] to lead [TEAM]', summary: '[TEAM] closes its search and moves into staff-building mode.' },
    { title: 'New era begins for [TEAM]', ticker: '[COACH] officially hired by [TEAM]', summary: '[TEAM] turns the page with [COACH] now running the program.' },
    { title: '[TEAM] picks [COACH] as next lead voice', ticker: 'SIDELINE UPDATE: [COACH] joins [TEAM]', summary: '[TEAM] believes [COACH] is the right fit for the next phase.' },
    { title: '[COACH] lands at [TEAM]', ticker: 'COACHING NEWS: [TEAM] chooses [COACH]', summary: '[TEAM] secures its top target and eyes a quick culture lift.' },
  ],
  promotion: [
    { title: '[COACH] jumps from [FROM_SCHOOL] to [TEAM]', ticker: 'POACH: [TEAM] pulls [COACH] from [FROM_SCHOOL]', summary: '[TEAM] wins a key carousel battle by grabbing [COACH].' },
    { title: '[TEAM] poaches [COACH]', ticker: 'MOVE: [COACH] leaves [FROM_SCHOOL] for [TEAM]', summary: '[COACH] climbs the ladder as [TEAM] opens a fresh chapter.' },
    { title: '[COACH] changes addresses', ticker: 'CAROUSEL CLIMB: [COACH] departs [FROM_SCHOOL]', summary: '[FROM_SCHOOL] now enters the vacancy queue after losing [COACH].' },
    { title: '[TEAM] wins high-profile coaching battle', ticker: '[COACH] accepts [TEAM] offer from [FROM_SCHOOL]', summary: '[TEAM] adds a proven winner while [FROM_SCHOOL] regroups.' },
    { title: '[COACH] takes the next rung at [TEAM]', ticker: 'PROMOTION: [COACH] exits [FROM_SCHOOL]', summary: '[COACH] trades up to [TEAM], creating a ripple vacancy behind him.' },
    { title: '[TEAM] lands promoted head coach', ticker: '[COACH] swaps [FROM_SCHOOL] for [TEAM]', summary: 'The carousel chain reaction grows after [COACH] takes the [TEAM] job.' },
  ],
  retirement: [
    { title: '[COACH] retires at [TEAM]', ticker: 'RETIREMENT: [COACH] steps away from [TEAM]', summary: '[COACH] closes a long run and leaves [TEAM] searching for continuity.' },
    { title: '[TEAM] loses veteran voice', ticker: '[COACH] calls it a career', summary: '[TEAM] now turns to succession planning after [COACH] retires.' },
    { title: '[COACH] exits coaching ranks', ticker: 'SIDELINE FAREWELL: [COACH] done at [TEAM]', summary: '[COACH] decides this offseason is the right time to walk away.' },
    { title: 'End of an era at [TEAM]', ticker: '[COACH] retires, [TEAM] opens search', summary: '[TEAM] enters a pivotal hire cycle after a notable retirement.' },
    { title: '[COACH] hangs it up', ticker: 'COACHING CAROUSEL: retirement at [TEAM]', summary: '[TEAM] joins the carousel after [COACH] steps down.' },
    { title: '[TEAM] begins life after [COACH]', ticker: '[COACH] announces retirement from [TEAM]', summary: 'A veteran departure sends [TEAM] into a critical offseason decision.' },
  ],
  resignation: [
    { title: '[COACH] steps away from [TEAM]', ticker: 'RESIGNATION: [COACH] exits [TEAM]', summary: '[COACH] leaves the sideline role and [TEAM] opens immediately.' },
    { title: '[TEAM] hit by surprise coaching exit', ticker: '[COACH] walks away at [TEAM]', summary: '[TEAM] gets an unexpected vacancy and must move fast in the carousel.' },
    { title: '[COACH] departs coaching post', ticker: 'OFFSEASON SHAKEUP: [COACH] leaves [TEAM]', summary: 'A sudden exit changes [TEAM] offseason priorities overnight.' },
    { title: '[TEAM] searching after voluntary exit', ticker: '[COACH] steps down from [TEAM]', summary: '[TEAM] enters the market after [COACH] opts out of coaching duties.' },
    { title: '[COACH] leaves [TEAM] role', ticker: 'CAROUSEL ALERT: [TEAM] vacancy after resignation', summary: '[TEAM] now competes for replacements after a non-firing departure.' },
    { title: 'Unexpected departure at [TEAM]', ticker: '[COACH] no longer leading [TEAM]', summary: '[TEAM] must reset quickly following [COACH] stepping away.' },
  ],
}

function replaceCarouselTokens(template: string, vars: { team: string; coach: string; from_school: string }): string {
  const from = vars.from_school || 'former school'
  return template
    .replaceAll('[TEAM]', vars.team || 'program')
    .replaceAll('[COACH]', vars.coach || 'coach')
    .replaceAll('[FROM_SCHOOL]', from)
}

function renderCarouselCopy(
  typ: string,
  vars: { team: string; coach: string; from_school: string; detail: string },
): { title: string; ticker: string; summary: string } {
  const bank = CAROUSEL_COPY_BANK[typ] ?? []
  if (!bank.length) {
    const fallback = vars.detail || 'Coaching carousel update'
    return {
      title: clipTicker(fallback, 72),
      ticker: clipTicker(fallback, 80),
      summary: clipTicker(fallback, 160),
    }
  }
  const pick = bank[Math.floor(Math.random() * bank.length)]
  return {
    title: clipTicker(replaceCarouselTokens(pick.title, vars), 72),
    ticker: clipTicker(replaceCarouselTokens(pick.ticker, vars), 80),
    summary: clipTicker(replaceCarouselTokens(pick.summary, vars), 160),
  }
}

const SPRING_STRONG = [
  'Sources say the team had a strong spring, with noticeable improvements across multiple position groups.',
  'Coaches are reportedly thrilled with the progress made during spring practices.',
  'Spring ball appears to have paid off, as several key units took a step forward.',
  'The program is gaining momentum after an impressive spring showing.',
]
const SPRING_MIXED = [
  'Spring ball produced mixed results, with some areas improving while others lagged behind.',
  'The team showed flashes of growth but still has work to do.',
  'Some position groups improved, but others failed to make a noticeable jump.',
]
const SPRING_WEAK = [
  'Spring practices raised concerns about the team overall development.',
  'Limited progress this spring leaves some question marks heading into the season.',
  'Several key areas failed to show meaningful improvement.',
]
const SPRING_BREAKOUT = [
  'A few under-the-radar players reportedly stood out during spring practices.',
  'One of the biggest takeaways from spring was the emergence of young talent.',
  'Spring ball may have reshaped the depth chart with a few surprise performances.',
]
const SPRING_TEAM_DYNAMIC = [
  '[TEAM] appears to have taken a step forward after a productive spring.',
  'Momentum is building within [TEAM] following strong spring practices.',
  '[TEAM] showed noticeable improvement across several key areas this spring.',
  'Spring results for [TEAM] were mixed, with both positives and concerns.',
  'Questions remain for [TEAM] after a relatively quiet spring.',
]

function pickOne<T>(arr: T[]): T {
  return arr[Math.floor(Math.random() * arr.length)]
}

function springFocusLabel(v: string, side: 'offense' | 'defense'): string {
  const off: Record<string, string> = {
    run_blocking: 'Run Blocking',
    pass_protection: 'Pass Protection',
    receiving: 'Receiving',
    pass_game: 'Pass Game',
    run_game: 'Run Game',
  }
  const def: Record<string, string> = {
    run_defense: 'Run Defense',
    pass_rush: 'Pass Rush',
    tackling: 'Tackling',
    pass_defense: 'Pass Defense',
    block_defeat: 'Block Defeat',
  }
  return side === 'offense' ? off[v] ?? v : def[v] ?? v
}

function springTone(summary: string): 'strong' | 'mixed' | 'weak' {
  const s = String(summary || '').toLowerCase()
  if (s.includes('excellent') || s.includes('solid')) return 'strong'
  if (s.includes('minor')) return 'mixed'
  return 'weak'
}

function ingestSpringBall(prev: any, next: any, center: ReturnType<typeof getNewsCenter>) {
  const p = prev?.offseason_spring_ball_results
  const n = next?.offseason_spring_ball_results
  if (!n || typeof n !== 'object') return
  if (JSON.stringify(p ?? null) === JSON.stringify(n ?? null)) return
  if (String(next?.season_phase ?? '').toLowerCase() !== 'offseason') return

  const year = Math.max(1, Number(next?.current_year ?? 1))
  const byTeam = (n?.by_team ?? {}) as Record<string, any>
  const teams = Object.keys(byTeam)
  if (!teams.length) return

  // League-level spring roundup
  const leagueKey = `spring:league:${year}:${teams.length}`
  if (center.tryConsumeKey(leagueKey)) {
    const id = nextId('art')
    const title = clipTicker(`Spring Ball Roundup: League Camps Wrap Up`, 72)
    const summary = clipTicker(pickOne(SPRING_BREAKOUT), 160)
    const content = [
      pickOne(SPRING_STRONG),
      '',
      'Spring camps wrapped with targeted development across the league and early depth-chart movement.',
      'Most programs reported subtle but meaningful growth in focus areas.',
    ].join('\n')
    const tickerText = clipTicker(`SPRING BALL: Camps close as teams report development gains`, 80)
    center.addArticleWithTicker(
      {
        id,
        title,
        summary,
        content,
        type: 'feature',
        teams: [],
        players: [],
        timestamp: Date.now(),
        priority: 55,
        tickerText,
        newsWeek: 0,
        seasonPhase: 'offseason',
        seasonYear: year,
      },
      {
        id,
        text: tickerText,
        type: 'ranking',
        priority: 'normal',
        relatedArticleId: id,
        newsWeek: 0,
        seasonPhase: 'offseason',
        seasonYear: year,
      },
    )
  }

  const userTeam = String(next?.user_team ?? '')
  const selected = new Set<string>()
  if (userTeam && byTeam[userTeam]) selected.add(userTeam)
  for (const t of teams) {
    if (selected.size >= 3) break
    selected.add(t)
  }
  for (const team of selected) {
    const r = byTeam[team] ?? {}
    const off = springFocusLabel(String(r?.offensive_focus ?? ''), 'offense')
    const de = springFocusLabel(String(r?.defensive_focus ?? ''), 'defense')
    const tone = springTone(String(r?.summary ?? ''))
    const bank = tone === 'strong' ? SPRING_STRONG : tone === 'mixed' ? SPRING_MIXED : SPRING_WEAK
    const dynamic = pickOne(SPRING_TEAM_DYNAMIC).replace('[TEAM]', team)
    const key = `spring:${year}:${team}:${off}:${de}:${r?.summary ?? ''}`
    if (!center.tryConsumeKey(key)) continue
    const id = nextId('art')
    const title = clipTicker(`${team}: Spring Focus Report`, 72)
    const notable = Array.isArray(r?.notable_players) ? r.notable_players.slice(0, 3) : []
    const notableText =
      notable.length > 0
        ? notable
            .map((n: any) => `${String(n?.position ?? '')} ${String(n?.player_name ?? '')}: +${Number(n?.delta ?? 0)} ${String(n?.attribute ?? '')}`)
            .join('; ')
        : 'No major standouts reported.'
    const content = [
      dynamic,
      '',
      `${pickOne(bank)}`,
      '',
      `Focuses: Offense ${off} | Defense ${de}.`,
      `Camp summary: ${String(r?.summary ?? 'Minor Improvement')}.`,
      `Notables: ${notableText}`,
    ].join('\n')
    const tickerText = clipTicker(`${team}: spring focus ${off}/${de} — ${String(r?.summary ?? 'Minor Improvement')}`, 80)
    center.addArticleWithTicker(
      {
        id,
        title,
        summary: clipTicker(dynamic, 160),
        content,
        type: 'feature',
        teams: [team],
        players: [],
        timestamp: Date.now(),
        priority: team === userTeam ? 70 : 52,
        tickerText,
        newsWeek: 0,
        seasonPhase: 'offseason',
        seasonYear: year,
      },
      {
        id,
        text: tickerText,
        type: 'recruiting',
        priority: team === userTeam ? 'high' : 'normal',
        relatedArticleId: id,
        newsWeek: 0,
        seasonPhase: 'offseason',
        seasonYear: year,
      },
    )
  }
}

function ingestYearTurn(prev: any, next: any, center: ReturnType<typeof getNewsCenter>) {
  const py = Number(prev?.current_year ?? 0)
  const ny = Number(next?.current_year ?? 0)
  if (ny > py && ny > 0 && center.tryConsumeKey(`yr:${ny}`)) {
    const id = nextId('art')
    const tickerText = clipTicker(`NEW SEASON: Year ${ny} opens across the state`, 80)
    const article: NewsArticle = {
      id,
      title: clipTicker(`Year ${ny}: New Faces, Same Rivalries`, 72),
      summary: 'Rosters reload, schedules harden, and the rankings board resets overnight.',
      content: [
        `The calendar flips to ${ny} — championship dreams are renewed everywhere.`,
        '',
        'Recruiting quiet period ends soon; expect visits, verbals, and portal buzz to spike.',
      ].join('\n'),
      type: 'recruiting',
      teams: [],
      players: [],
      timestamp: Date.now(),
      priority: 35,
      tickerText,
      newsWeek: 0,
      seasonPhase: String(next?.season_phase ?? '').toLowerCase() || 'offseason',
      seasonYear: ny,
    }
    center.addArticleWithTicker(article, {
      id,
      text: tickerText,
      type: 'recruiting',
      priority: 'low',
      relatedArticleId: id,
      newsWeek: 0,
      seasonPhase: article.seasonPhase,
      seasonYear: ny,
    })
  }
}

const PLAYOFF_CLINCH_MESSAGES = [
  '[TEAM] punches a playoff ticket and the sideline energy is obvious.',
  '[TEAM] survives the regular-season grind and earns a postseason berth.',
  '[TEAM] officially locks in and keeps its title path alive.',
  '[TEAM] closes the door on the bubble and grabs a playoff slot.',
  '[TEAM] books a playoff date after a steady closing stretch.',
  '[TEAM] confirms postseason football for its community.',
  '[TEAM] turns a strong fall into a playoff reward.',
  '[TEAM] gets in, and now the matchup board starts mattering.',
  '[TEAM] secures enough results to reach the bracket.',
  '[TEAM] is playoff-bound after finishing business late.',
  '[TEAM] has clinched and now shifts fully to knockout prep.',
  '[TEAM] celebrates a postseason berth after a statement finish.',
  '[TEAM] heads to the playoffs with momentum building internally.',
  '[TEAM] earns a spot in the field and keeps championship hopes alive.',
  '[TEAM] makes the cut and enters the postseason conversation.',
  '[TEAM] is through to the bracket after a resilient campaign.',
  '[TEAM] claims a postseason seat with timely wins.',
  '[TEAM] locks up playoff football and embraces the pressure.',
  '[TEAM] keeps the dream alive with a confirmed playoff berth.',
  '[TEAM] turns regular-season consistency into playoff access.',
]

const PLAYOFF_SNUB_MESSAGES = [
  '[TEAM] misses the playoff field and frustration rises around the program.',
  '[TEAM] falls short of the bracket, and community pressure is mounting.',
  '[TEAM] is left out despite expectations, creating immediate offseason heat.',
  '[TEAM] misses out and now faces hard questions from supporters.',
  '[TEAM] lands outside the playoff line, and patience is thin.',
  '[TEAM] is out, and pressure around leadership just increased.',
  '[TEAM] narrowly misses postseason play, sparking intense local criticism.',
  '[TEAM] expected to be in, but the bracket leaves them home.',
  '[TEAM] misses the cut and enters an uneasy offseason.',
  '[TEAM] comes up short, and calls for a reset grow louder.',
  '[TEAM] is on the outside looking in, with fan pressure building.',
  '[TEAM] misses playoffs and now faces a credibility challenge.',
  '[TEAM] falls off the playoff map late, drawing sharp reaction.',
  '[TEAM] does not qualify, and scrutiny around the staff spikes.',
  '[TEAM] is left behind on selection day, and temperature rises.',
  '[TEAM] fails to convert promise into a playoff berth.',
  '[TEAM] exits regular season without a berth and with major noise outside.',
  '[TEAM] misses postseason football, putting the offseason under a microscope.',
  '[TEAM] is snubbed by the final field and community expectations remain high.',
  '[TEAM] ends up short of the bracket, and pressure now follows every move.',
]

function enteredPlayoffs(prev: any, next: any): boolean {
  const pPrev = String(prev?.season_phase ?? '').toLowerCase()
  const pNext = String(next?.season_phase ?? '').toLowerCase()
  if (pPrev !== 'playoffs' && pNext === 'playoffs') return true
  const prevSeeds = playoffSeeds(prev)
  const nextSeeds = playoffSeeds(next)
  return prevSeeds.size === 0 && nextSeeds.size > 0
}

function ingestPlayoffFieldNews(prev: any, next: any, center: ReturnType<typeof getNewsCenter>) {
  if (!enteredPlayoffs(prev, next)) return
  const year = Math.max(1, Number(next?.current_year ?? 1))
  const seedsNow = playoffSeeds(next)
  const seedsPrev = playoffSeeds(prev)
  const inField = new Set<string>(Array.from(seedsNow.keys()))
  if (!inField.size) return

  const newClinchers =
    seedsPrev.size > 0 ? Array.from(inField).filter((t) => !seedsPrev.has(t)) : Array.from(inField)

  for (const team of newClinchers.slice(0, 8)) {
    const key = `playoff:clinch:${year}:${team}`
    if (!center.tryConsumeKey(key)) continue
    const id = nextId('art')
    const seed = seedsNow.get(team)
    const seedLabel = seed && seed > 0 ? `#${seed}` : 'Playoff'
    const summary = pickOne(PLAYOFF_CLINCH_MESSAGES).replaceAll('[TEAM]', team)
    const tickerText = clipTicker(`${seedLabel} ${team} clinches playoff berth`, 80)
    center.addArticleWithTicker(
      {
        id,
        title: clipTicker(`${team} clinches playoff berth`, 72),
        summary: clipTicker(summary, 160),
        content: [summary, '', `${team} now turns to matchup prep and postseason execution.`].join('\n'),
        type: 'ranking',
        teams: [team],
        players: [],
        timestamp: Date.now(),
        priority: 72,
        tickerText,
        newsWeek: 0,
        seasonPhase: 'playoffs',
        seasonYear: year,
      },
      {
        id,
        text: tickerText,
        type: 'ranking',
        priority: 'normal',
        relatedArticleId: id,
        newsWeek: 0,
        seasonPhase: 'playoffs',
        seasonYear: year,
      },
    )
  }

  const standings = next?.standings ?? {}
  const rankMap = teamRankMap(next)
  const snubs = Object.keys(standings)
    .filter((t) => !inField.has(t))
    .map((t) => {
      const s = standings[t] ?? {}
      const wins = Number(s?.wins ?? 0)
      const losses = Number(s?.losses ?? 0)
      const pd = Number(s?.points_for ?? 0) - Number(s?.points_against ?? 0)
      const rank = rankMap.get(t) ?? 99
      return { team: t, wins, losses, pd, rank }
    })
    .filter((r) => r.rank <= 6 || r.wins >= 7 || (r.wins >= 6 && r.pd > 0))
    .sort((a, b) => {
      if (a.rank !== b.rank) return a.rank - b.rank
      if (b.wins !== a.wins) return b.wins - a.wins
      return b.pd - a.pd
    })
    .slice(0, 5)

  for (const row of snubs) {
    const key = `playoff:snub:${year}:${row.team}`
    if (!center.tryConsumeKey(key)) continue
    const id = nextId('art')
    const summary = pickOne(PLAYOFF_SNUB_MESSAGES).replaceAll('[TEAM]', row.team)
    const tickerText = clipTicker(`SNUB WATCH: ${row.team} misses playoffs at ${row.wins}-${row.losses}`, 80)
    center.addArticleWithTicker(
      {
        id,
        title: clipTicker(`${row.team} misses playoff field`, 72),
        summary: clipTicker(summary, 160),
        content: [
          summary,
          '',
          `${row.team} closes the regular season at ${row.wins}-${row.losses}.`,
          'Community pressure and offseason decisions now become central storylines.',
        ].join('\n'),
        type: 'feature',
        teams: [row.team],
        players: [],
        timestamp: Date.now(),
        priority: 78,
        tickerText,
        breaking: true,
        newsWeek: 0,
        seasonPhase: 'playoffs',
        seasonYear: year,
      },
      {
        id,
        text: tickerText,
        type: 'ranking',
        priority: 'high',
        relatedArticleId: id,
        newsWeek: 0,
        seasonPhase: 'playoffs',
        seasonYear: year,
      },
    )
  }
}

function isPreseasonPredictionWindow(state: any): boolean {
  const phase = String(state?.season_phase ?? '').toLowerCase()
  const week = Number(state?.current_week ?? 1)
  return phase === 'preseason' || (phase === 'regular' && week <= 1)
}

function lastSeasonRowsByTeam(leagueHistory?: any): Map<string, any> {
  const seasons = Array.isArray(leagueHistory?.seasons) ? leagueHistory.seasons : []
  if (!seasons.length) return new Map<string, any>()
  const sorted = [...seasons].sort((a: any, b: any) => Number(b?.year ?? 0) - Number(a?.year ?? 0))
  const last = sorted[0] ?? {}
  const standings = Array.isArray(last?.standings) ? last.standings : []
  const map = new Map<string, any>()
  for (const row of standings) {
    const team = String(row?.team ?? '')
    if (!team) continue
    map.set(team, row)
  }
  const champion = String(last?.state_champion ?? '')
  const runnerUp = String(last?.runner_up ?? '')
  if (champion && map.has(champion)) map.set(champion, { ...map.get(champion), __postseason: 'champion' })
  if (runnerUp && map.has(runnerUp)) map.set(runnerUp, { ...map.get(runnerUp), __postseason: 'runner_up' })
  return map
}

function predictionScore(team: any, standing: any, lastSeason: any): number {
  const prestige = Number(team?.prestige ?? 5)
  const coach = team?.coach ?? {}
  const coachSkill =
    Number(coach?.playcalling ?? 5) +
    Number(coach?.scheme_teach ?? 5) +
    Number(coach?.motivating ?? 5) +
    Number(coach?.discipline ?? 5) +
    Number(coach?.development ?? 5)
  const wins = Number(standing?.wins ?? 0)
  const losses = Number(standing?.losses ?? 0)
  const pf = Number(standing?.points_for ?? 0)
  const pa = Number(standing?.points_against ?? 0)
  const margin = pf - pa
  const lastWins = Number(lastSeason?.wins ?? 0)
  const lastLosses = Number(lastSeason?.losses ?? 0)
  const lastPd =
    Number(lastSeason?.point_diff ?? Number(lastSeason?.points_for ?? 0) - Number(lastSeason?.points_against ?? 0))
  const postseason = String(lastSeason?.__postseason ?? '')
  const postseasonBonus = postseason === 'champion' ? 30 : postseason === 'runner_up' ? 18 : 0
  return (
    prestige * 9 +
    coachSkill * 1.6 +
    lastWins * 10 -
    lastLosses * 4 +
    lastPd * 0.06 +
    postseasonBonus +
    wins * 4 -
    losses * 2 +
    margin * 0.02
  )
}

function ingestPreseasonPredictions(prev: any, next: any, center: ReturnType<typeof getNewsCenter>, leagueHistory?: any) {
  if (!isPreseasonPredictionWindow(next)) return
  if (isPreseasonPredictionWindow(prev)) return
  const teams = Array.isArray(next?.teams) ? next.teams : []
  if (!teams.length) return
  const year = Math.max(1, Number(next?.current_year ?? 1))
  const standings = next?.standings ?? {}
  const lastByTeam = lastSeasonRowsByTeam(leagueHistory)
  const grouped = new Map<string, any[]>()
  for (const t of teams) {
    const cls = String(t?.classification ?? '').trim() || 'Unclassified'
    if (!grouped.has(cls)) grouped.set(cls, [])
    grouped.get(cls)!.push(t)
  }
  const classes = Array.from(grouped.keys()).sort((a, b) => a.localeCompare(b))
  for (const cls of classes) {
    const classTeams = grouped.get(cls) ?? []
    const top = classTeams
      .map((t) => {
        const name = String(t?.name ?? '')
        return {
          team: name,
          score: predictionScore(t, standings?.[name] ?? {}, lastByTeam.get(name) ?? {}),
          prestige: Number(t?.prestige ?? 5),
        }
      })
      .filter((r) => r.team)
      .sort((a, b) => b.score - a.score)
      .slice(0, 10)
    if (!top.length) continue
    const key = `pred:${year}:${cls}:${top.map((t) => t.team).join('|')}`
    if (!center.tryConsumeKey(key)) continue
    const id = nextId('art')
    const lines = top.map((row, idx) => `${idx + 1}. ${row.team} (Prestige ${row.prestige})`)
    const title = clipTicker(`Preseason ${cls} Top 10 Projection`, 72)
    const summary = clipTicker(`Early outlook: ${top.slice(0, 3).map((t) => t.team).join(', ')} lead the ${cls} preseason board.`, 160)
    const tickerText = clipTicker(`PRESEASON ${cls}: #1 ${top[0].team}, #2 ${top[1]?.team ?? '—'}, #3 ${top[2]?.team ?? '—'}`, 80)
    center.addArticleWithTicker(
      {
        id,
        title,
        summary,
        content: [`Preseason prediction board for ${cls}:`, '', ...lines, '', 'These projections blend program prestige and staff profile entering Week 1.'].join('\n'),
        type: 'ranking',
        teams: top.map((t) => t.team),
        players: [],
        timestamp: Date.now(),
        priority: 68,
        tickerText,
        newsWeek: 0,
        seasonPhase: String(next?.season_phase ?? '').toLowerCase() || 'preseason',
        seasonYear: year,
      },
      {
        id,
        text: tickerText,
        type: 'ranking',
        priority: 'normal',
        relatedArticleId: id,
        newsWeek: 0,
        seasonPhase: String(next?.season_phase ?? '').toLowerCase() || 'preseason',
        seasonYear: year,
      },
    )
  }
}

function appendRegularSeasonGameNews(
  center: ReturnType<typeof getNewsCenter>,
  state: any,
  wi: number,
  gi: number,
  ranks: Map<string, number>,
  streakSent: Set<string>,
): void {
  const phase = String(state?.season_phase ?? '').toLowerCase()
  if (phase !== 'regular' && phase !== 'playoffs') return

  const weeks = state?.weeks ?? []
  const nw = state?.week_results ?? []
  const nr = nw[wi] ?? []
  const wk = weeks[wi] ?? []
  if (gi >= nr.length) return
  if (!nr[gi]?.played) return

  const g = wk[gi] ?? {}
  const home = String(g?.home ?? '')
  const away = String(g?.away ?? '')
  if (!home || !away) return
  const hs = Number(nr[gi]?.home_score ?? 0)
  const ash = Number(nr[gi]?.away_score ?? 0)
  if (!center.tryConsumeKey(`wr:${wi}:${gi}:${home}:${away}:${hs}:${ash}`)) return

  const seasonYear = Math.max(1, Number(state?.current_year ?? 1))
  const ot = Boolean(nr[gi]?.ot)
  const stats = (nr[gi]?.player_stats ?? []) as PlayerGameLine[]
  const weekLabel = `Week ${wi + 1}`
  const leagueWeek = wi + 1
  const { article, meta, standout } = buildRecapArticle({
    home,
    away,
    hs,
    ash,
    ot,
    weekLabel,
    ranks,
    playerStats: Array.isArray(stats) ? stats : [],
    leagueWeek,
    seasonYear,
    seasonPhase: phase,
  })
  const prTicker: TickerPriority = priorityForGame(meta)

  center.addArticleWithTicker(article, {
    id: article.id,
    text: clipTicker(article.tickerText, 80),
    type: meta.upset ? 'upset' : standout ? 'player' : 'score',
    priority: prTicker,
    relatedArticleId: article.id,
    newsWeek: leagueWeek,
    seasonPhase: phase,
    seasonYear,
  })

  const win = winnerFromScores(home, away, hs, ash)
  const statLine = standout && meta.bigPlayer ? clipTicker(standout.line, 80) : ''
  const recapLower = clipTicker(article.tickerText, 80).toLowerCase()
  if (statLine && statLine.toLowerCase() !== recapLower) {
    center.pushTicker({
      text: statLine,
      type: 'player',
      priority: 'normal',
      relatedArticleId: article.id,
      newsWeek: leagueWeek,
      seasonPhase: phase,
      seasonYear,
    })
  }

  if (win) {
    const streak = computeWinStreak(state, win)
    if (streak >= 3) {
      const sk = `${win}:${streak}`
      if (!streakSent.has(sk)) {
        streakSent.add(sk)
        center.pushTicker({
          text: clipTicker(`${win} wins ${streak} straight`, 80),
          type: 'ranking',
          priority: streak >= 5 ? 'high' : 'normal',
          newsWeek: leagueWeek,
          seasonPhase: phase,
          seasonYear,
        })
      }
    }
  }
}

/**
 * Hydrate ticker + feed from an already-loaded save (no new sim yet).
 * Uses the same dedupe keys as live ingest so simming later won't double-post.
 */
export function seedNewsFromSaveState(state: any, saveId: string, leagueHistory?: any) {
  if (!state || !saveId) return
  const center = getNewsCenter(saveId)
  const phase = String(state?.season_phase ?? '').toLowerCase()
  const cw = Math.max(1, Number(state?.current_week ?? 1))
  const low = Math.max(1, cw - 2)
  const high = cw + 2

  ingestScrimmages({ preseason_scrimmages: [] }, state, center)
  ingestCarousel({ offseason_coach_carousel_last_events: [] }, state, center)
  ingestTransfers({ offseason_transfer_news_events: [] }, state, center)
  ingestSpringBall({ offseason_spring_ball_results: null }, state, center)
  ingestPlayoffGame({ playoffs: {} }, state, center)
  ingestPlayoffFieldNews({ season_phase: 'regular', playoffs: {} }, state, center)
  ingestPreseasonPredictions({ season_phase: '' }, state, center, leagueHistory)

  if (phase !== 'regular' && phase !== 'playoffs') return

  const ranks = teamRankMap(state)
  const nw = state?.week_results ?? []
  const streakSent = new Set<string>()

  for (let wi = high - 1; wi >= low - 1; wi--) {
    if (wi < 0 || wi >= nw.length) continue
    const nr = nw[wi] ?? []
    for (let gi = 0; gi < nr.length; gi++) {
      appendRegularSeasonGameNews(center, state, wi, gi, ranks, streakSent)
    }
  }
}

export function ingestStateNews(prev: any, next: any, saveId: string, leagueHistory?: any) {
  if (!next || !saveId) return
  const center = getNewsCenter(saveId)
  const phase = String(next?.season_phase ?? '').toLowerCase()

  ingestYearTurn(prev, next, center)
  ingestCarousel(prev, next, center)
  ingestTransfers(prev, next, center)
  ingestSpringBall(prev, next, center)
  ingestScrimmages(prev, next, center)
  ingestPreseasonPredictions(prev, next, center, leagueHistory)
  ingestPlayoffFieldNews(prev, next, center)
  ingestPlayoffGame(prev, next, center)

  if (phase !== 'regular' && phase !== 'playoffs') {
    return
  }

  const ranks = teamRankMap(prev)
  const pw = prev?.week_results ?? []
  const nw = next?.week_results ?? []
  const streakSent = new Set<string>()

  for (let wi = 0; wi < nw.length; wi++) {
    const pr = pw[wi] ?? []
    const nr = nw[wi] ?? []
    for (let gi = 0; gi < nr.length; gi++) {
      if (!nr[gi]?.played || pr[gi]?.played) continue
      appendRegularSeasonGameNews(center, next, wi, gi, ranks, streakSent)
    }
  }
}
