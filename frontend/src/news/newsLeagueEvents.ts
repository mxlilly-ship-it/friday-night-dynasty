import type { NewsArticle } from './newsTypes'
import { clipTicker, getNewsCenter, nextId } from './newsStore'

type ProspectRow = {
  name: string
  team: string
  classification: string
  region: string
  position: string
  potential: number
  overall: number
}

function schedulingPodKey(cls: unknown, region: unknown): string {
  const c = String(cls ?? 'UNK').trim() || 'UNK'
  const r = String(region ?? 'State').trim() || 'State'
  return `${c}|${r}`
}

function standingsSortKey(team: string, standings: Record<string, any>): [number, number, number, string] {
  const s = standings[team] ?? {}
  const w = Number(s?.wins ?? 0)
  const pf = Number(s?.points_for ?? 0)
  const pa = Number(s?.points_against ?? 0)
  return [-w, -(pf - pa), -pf, team]
}

export function computeRegionalChampions(state: any): Array<{ team: string; classification: string; region: string }> {
  const teams = Array.isArray(state?.teams) ? state.teams : []
  const standings = state?.standings ?? {}
  const pods = new Map<string, string[]>()
  const meta = new Map<string, { classification: string; region: string }>()

  for (const t of teams) {
    if (!t || typeof t !== 'object') continue
    const name = String(t.name ?? '').trim()
    if (!name) continue
    const cls = String(t.classification ?? 'UNK').trim() || 'UNK'
    const reg = String(t.region ?? 'State').trim() || 'State'
    const key = schedulingPodKey(cls, reg)
    if (!pods.has(key)) pods.set(key, [])
    pods.get(key)!.push(name)
    if (!meta.has(key)) meta.set(key, { classification: cls, region: reg })
  }

  const out: Array<{ team: string; classification: string; region: string }> = []
  for (const [key, names] of pods) {
    const inSt = names.filter((n) => n in standings)
    if (!inSt.length) continue
    inSt.sort((a, b) => {
      const ka = standingsSortKey(a, standings)
      const kb = standingsSortKey(b, standings)
      for (let i = 0; i < ka.length; i++) {
        if (ka[i] !== kb[i]) return ka[i] < kb[i] ? -1 : 1
      }
      return 0
    })
    const m = meta.get(key)!
    out.push({ team: inSt[0], classification: m.classification, region: m.region })
  }
  return out.sort((a, b) => a.classification.localeCompare(b.classification) || a.region.localeCompare(b.region))
}

function isFreshmanYear(year: unknown): boolean {
  const n = Number(year)
  return n === 9 || n === 1
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

function potentialTier(pot: number): { label: string; minHeadline: number } {
  if (pot >= 96) return { label: 'generational', minHeadline: 96 }
  if (pot >= 86) return { label: 'elite', minHeadline: 86 }
  if (pot >= 76) return { label: 'all-state', minHeadline: 76 }
  if (pot >= 66) return { label: 'solid', minHeadline: 66 }
  return { label: 'role', minHeadline: 999 }
}

function collectFreshmanProspects(state: any): ProspectRow[] {
  const teams = Array.isArray(state?.teams) ? state.teams : []
  const rows: ProspectRow[] = []
  for (const t of teams) {
    if (!t || typeof t !== 'object') continue
    const teamName = String(t.name ?? '').trim()
    if (!teamName) continue
    const cls = String(t.classification ?? '').trim()
    const reg = String(t.region ?? '').trim()
    const roster = Array.isArray(t.roster) ? t.roster : []
    for (const p of roster) {
      if (!p || typeof p !== 'object') continue
      if (!isFreshmanYear(p.year)) continue
      const name = String(p.name ?? '').trim()
      if (!name) continue
      rows.push({
        name,
        team: teamName,
        classification: cls || '—',
        region: reg || '—',
        position: String(p.position ?? 'ATH').trim() || 'ATH',
        potential: Number(p.potential ?? 50),
        overall: Math.round(playerOverall(p as Record<string, unknown>)),
      })
    }
  }
  return rows.sort((a, b) => b.potential - a.potential || b.overall - a.overall || a.name.localeCompare(b.name))
}

function addArticle(
  center: ReturnType<typeof getNewsCenter>,
  article: NewsArticle,
  tickerType: 'score' | 'player' | 'upset' | 'injury' | 'recruiting' | 'ranking' = 'recruiting',
  priority: 'low' | 'normal' | 'high' = 'normal',
) {
  center.addArticleWithTicker(article, {
    id: article.id,
    text: clipTicker(article.tickerText, 80),
    type: tickerType,
    priority: article.breaking ? 'high' : priority,
    relatedArticleId: article.id,
    newsWeek: article.newsWeek,
    seasonPhase: article.seasonPhase,
    seasonYear: article.seasonYear,
  })
}

export function ingestRegionalTitles(prev: any, next: any, center: ReturnType<typeof getNewsCenter>) {
  const prevPhase = String(prev?.season_phase ?? '').toLowerCase()
  const nextPhase = String(next?.season_phase ?? '').toLowerCase()
  const entered = (prevPhase !== 'playoffs' && nextPhase === 'playoffs') || enteredPlayoffsSeeds(prev, next)
  if (!entered) return

  const year = Math.max(1, Number(next?.current_year ?? 1))
  const winners = computeRegionalChampions(next)
  for (const w of winners) {
    const key = `regional:${year}:${w.classification}:${w.region}:${w.team}`
    if (!center.tryConsumeKey(key)) continue
    const st = next?.standings?.[w.team] ?? {}
    const rec = `${Number(st?.wins ?? 0)}-${Number(st?.losses ?? 0)}`
    const id = nextId('art')
    const title = clipTicker(`${w.team} wins ${w.region} ${w.classification} regional title (${rec})`, 72)
    const tickerText = clipTicker(`REGION: ${w.team} tops ${w.region} ${w.classification} pod`, 80)
    addArticle(
      center,
      {
        id,
        title,
        summary: clipTicker(
          `${w.team} finished the regular season ahead of every ${w.classification} foe in the ${w.region} pod at ${rec}.`,
          160,
        ),
        content: [
          `${w.team} claims the ${w.region} ${w.classification} regional crown with a ${rec} regular-season mark.`,
          '',
          'Pod standings set the playoff bracket — this program enters the postseason with local bragging rights.',
        ].join('\n'),
        type: 'ranking',
        teams: [w.team],
        players: [],
        timestamp: Date.now(),
        priority: 62,
        tickerText,
        newsWeek: 0,
        seasonPhase: 'playoffs',
        seasonYear: year,
      },
      'ranking',
    )
  }
}

function enteredPlayoffsSeeds(prev: any, next: any): boolean {
  const prevSeeds = playoffSeedCount(prev)
  const nextSeeds = playoffSeedCount(next)
  return prevSeeds === 0 && nextSeeds > 0
}

function playoffSeedCount(state: any): number {
  const po = state?.playoffs
  if (!po || typeof po !== 'object') return 0
  if (Array.isArray(po.seeds)) return po.seeds.length
  const by = po.by_class
  if (!by || typeof by !== 'object') return 0
  let n = 0
  for (const v of Object.values(by)) {
    const seeds = (v as any)?.seeds
    if (Array.isArray(seeds)) n += seeds.length
  }
  return n
}

export function ingestChampionship(prev: any, next: any, center: ReturnType<typeof getNewsCenter>) {
  const prevPo = prev?.playoffs
  const nextPo = next?.playoffs
  const champ = String(nextPo?.champion ?? '').trim()
  const runner = String(nextPo?.runner_up ?? '').trim()
  if (!champ) return

  const prevDone = Boolean(prevPo?.completed)
  const nextDone = Boolean(nextPo?.completed)
  if (!nextDone) return
  if (prevDone && String(prevPo?.champion ?? '') === champ) return

  const year = Math.max(1, Number(next?.current_year ?? 1))
  const key = `champ:${year}:${champ}`
  if (!center.tryConsumeKey(key)) return

  const id = nextId('art')
  const title = clipTicker(`${champ} wins ${year} state championship`, 72)
  const tickerText = clipTicker(`TITLE: ${champ} wins state championship`, 80)
  const summary = runner
    ? clipTicker(`${champ} finishes the year as state champion, topping ${runner} in the final bracket.`, 160)
    : clipTicker(`${champ} finishes the year as state champion.`, 160)

  addArticle(
    center,
    {
      id,
      title,
      summary,
      content: [
        `${champ} is your ${year} state champion.`,
        runner ? `Runner-up: ${runner}.` : '',
        '',
        'The bracket is complete — trophy cases update statewide as the calendar turns toward the offseason.',
      ]
        .filter(Boolean)
        .join('\n'),
      type: 'feature',
      teams: [champ, runner].filter(Boolean),
      players: [],
      timestamp: Date.now(),
      priority: 95,
      tickerText,
      breaking: true,
      newsWeek: 0,
      seasonPhase: String(next?.season_phase ?? 'playoffs').toLowerCase(),
      seasonYear: year,
    },
    'ranking',
    'high',
  )
}

export function ingestGraduationAndFreshmen(prev: any, next: any, center: ReturnType<typeof getNewsCenter>) {
  const prevReport = prev?.offseason_graduation_report
  const nextReport = next?.offseason_graduation_report
  if (!nextReport || typeof nextReport !== 'object') return
  if (prevReport && typeof prevReport === 'object' && Object.keys(prevReport).length > 0) return

  const year = Math.max(1, Number(next?.current_year ?? 1))
  const phase = String(next?.season_phase ?? 'offseason').toLowerCase()

  // Graduation league summary
  const gradKey = `grad:league:${year}`
  if (center.tryConsumeKey(gradKey)) {
    let totalGrads = 0
    const notable: Array<{ name: string; team: string; position: string; ovr: number }> = []
    for (const [team, list] of Object.entries(nextReport as Record<string, unknown[]>)) {
      const players = Array.isArray(list) ? list : []
      totalGrads += players.length
      for (const p of players) {
        if (!p || typeof p !== 'object') continue
        const name = String((p as any).name ?? '').trim()
        if (!name) continue
        const ovr = Math.round(playerOverall(p as Record<string, unknown>))
        if (ovr >= 72) {
          notable.push({
            name,
            team,
            position: String((p as any).position ?? '—'),
            ovr,
          })
        }
      }
    }
    notable.sort((a, b) => b.ovr - a.ovr)
    const id = nextId('art')
    const tickerText = clipTicker(`GRADUATION: ${totalGrads} seniors depart statewide`, 80)
    const lines = notable.slice(0, 12).map((p) => `• ${p.name} (${p.position}, ${p.team}) — OVR ${p.ovr}`)
    addArticle(
      center,
      {
        id,
        title: clipTicker(`Graduation wave: ${totalGrads} seniors leave programs statewide`, 72),
        summary: clipTicker(
          notable.length
            ? `Programs reload after ${totalGrads} senior departures; ${notable[0].name} among notable graduations.`
            : `${totalGrads} seniors graduate as rosters turn over for ${year}.`,
          160,
        ),
        content: [
          `Graduation day across the state: ${totalGrads} seniors move on.`,
          '',
          notable.length ? 'Notable graduations:' : 'Depth charts reset as underclassmen step into larger roles.',
          ...lines,
        ].join('\n'),
        type: 'feature',
        teams: [],
        players: notable.slice(0, 8).map((p) => p.name),
        timestamp: Date.now(),
        priority: 58,
        tickerText,
        newsWeek: 0,
        seasonPhase: phase,
        seasonYear: year,
      },
      'player',
    )
  }

  // Freshman class — statewide prospect headlines
  const prospects = collectFreshmanProspects(next)
  if (!prospects.length) return

  const classKey = `freshman:radar:${year}`
  if (center.tryConsumeKey(classKey)) {
    const top = prospects.slice(0, 15)
    const id = nextId('art')
    const tickerText = clipTicker(
      `FRESHMAN RADAR: ${top[0]?.name ?? '—'} (${top[0]?.potential ?? '—'} pot) leads incoming class`,
      80,
    )
    const lines = top.map(
      (p, i) =>
        `${i + 1}. ${p.name} (${p.position}, ${p.team}) — Pot ${p.potential}, OVR ${p.overall} · ${p.classification} ${p.region}`,
    )
    addArticle(
      center,
      {
        id,
        title: clipTicker(`Freshman class radar: state's top incoming prospects`, 72),
        summary: clipTicker(
          `Early look at ${year} newcomers — ${top.slice(0, 3).map((p) => p.name).join(', ')} head the statewide list.`,
          160,
        ),
        content: ['Statewide freshman prospect board (by potential):', '', ...lines, '', 'Programs will sort depth charts all spring.'].join(
          '\n',
        ),
        type: 'recruiting',
        teams: top.map((p) => p.team),
        players: top.map((p) => p.name),
        timestamp: Date.now(),
        priority: 74,
        tickerText,
        newsWeek: 0,
        seasonPhase: phase,
        seasonYear: year,
      },
      'recruiting',
      'high',
    )
  }

  const headlineProspects = prospects.filter((p) => p.potential >= 76).slice(0, 28)
  for (const p of headlineProspects) {
    const tier = potentialTier(p.potential)
    const key = `freshman:${year}:${p.team}:${p.name}:${p.potential}`
    if (!center.tryConsumeKey(key)) continue
    const id = nextId('art')
    let title: string
    let tickerText: string
    let summary: string
    if (tier.label === 'generational') {
      title = clipTicker(`GENERATIONAL: ${p.name} (${p.position}) arrives at ${p.team}`, 72)
      tickerText = clipTicker(`FRESHMAN: Generational ${p.name} (${p.position}) → ${p.team}`, 80)
      summary = clipTicker(
        `${p.name} enters ${p.team} with generational ceiling (Pot ${p.potential}) — statewide buzz is immediate.`,
        160,
      )
    } else if (tier.label === 'elite') {
      title = clipTicker(`Elite incoming: ${p.name} (${p.position}) joins ${p.team}`, 72)
      tickerText = clipTicker(`FRESHMAN: Elite ${p.name} (${p.position}) lands at ${p.team}`, 80)
      summary = clipTicker(
        `${p.name} (${p.position}) brings elite upside (Pot ${p.potential}) to ${p.team}'s ${p.classification} roster.`,
        160,
      )
    } else {
      title = clipTicker(`${p.name} (${p.position}) tabbed top ${p.classification} incoming prospect`, 72)
      tickerText = clipTicker(`FRESHMAN: ${p.name} (${p.position}, Pot ${p.potential}) → ${p.team}`, 80)
      summary = clipTicker(
        `${p.name} profiles as an all-state caliber freshman pickup for ${p.team} (Pot ${p.potential}, OVR ${p.overall}).`,
        160,
      )
    }
    addArticle(
      center,
      {
        id,
        title,
        summary,
        content: [
          `${p.name} · ${p.position} · ${p.team} (${p.classification}, ${p.region})`,
          `Potential ${p.potential} · Current OVR ${p.overall}`,
          '',
          tier.label === 'generational'
            ? 'Coaches statewide are already asking how soon this name can impact Friday nights.'
            : 'Spring installs will determine how quickly this prospect climbs the depth chart.',
        ].join('\n'),
        type: 'recruiting',
        teams: [p.team],
        players: [p.name],
        timestamp: Date.now(),
        priority: tier.label === 'generational' ? 88 : tier.label === 'elite' ? 80 : 68,
        tickerText,
        breaking: tier.label === 'generational',
        newsWeek: 0,
        seasonPhase: phase,
        seasonYear: year,
      },
      'recruiting',
      tier.label === 'generational' || tier.label === 'elite' ? 'high' : 'normal',
    )
  }
}

export function seedLeagueEventNews(state: any, center: ReturnType<typeof getNewsCenter>) {
  ingestRegionalTitles({ season_phase: 'regular', playoffs: {} }, state, center)
  ingestChampionship({ playoffs: {} }, state, center)
  ingestGraduationAndFreshmen({}, state, center)
}
