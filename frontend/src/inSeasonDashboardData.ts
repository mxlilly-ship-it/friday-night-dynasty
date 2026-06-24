import { buildScoutingReportBundle } from './scoutingReportEngine'
import type { NewsArticle } from './news/newsTypes'

export type ScheduleRow = {
  week: number
  opponent: string
  played: boolean
  scoreLine: string
  isRegionGame: boolean
  userHome: boolean
  homeThemeLabel: string | null
}

export type StandingsRow = {
  rank: number
  teamName: string
  wins: number
  losses: number
  pointsFor: number
  pointsAgainst: number
  diff: number
  ppg: number
  ppgd: number
}

export type LastGameRecap = {
  week: number
  opponent: string
  userHome: boolean
  userScore: number
  oppScore: number
  won: boolean
  ot: boolean
  headline: string
  passYds: number
  rushYds: number
  tds: number
  interceptions: number
  sacks: number
  compPct: number | null
}

export type GoalTile = {
  name: string
  status: 'on' | 'track' | 'off'
  statusLabel: string
  progressPct: number
  description: string
  sub: string
}

export type InboxPreviewItem = {
  id: string
  title: string
  sub: string
  linkLabel: string
  urgency: 'now' | 'soon' | 'done' | 'info'
  week: number
}

export type TaggedNewsRow = {
  id: string
  tag: string
  tagClass: string
  headline: string
}

function findTeam(state: any, teamName: string) {
  return (state?.teams ?? []).find((t: { name?: string }) => t?.name === teamName) ?? null
}

/** Returns stadium_name from team/save data only — blank when not set in JSON. */
export function teamStadiumName(team: any): string {
  return String(team?.stadium_name ?? '').trim()
}

export function teamRecordLine(state: any, teamName: string): string {
  const s = state?.standings?.[teamName]
  if (!s) return '0-0'
  return `${Number(s.wins ?? 0)}-${Number(s.losses ?? 0)}`
}

function teamDisplayName(team: any, fallback: string): string {
  const nick = String(team?.nickname ?? '').trim()
  return nick || fallback
}

function sumPlayerStatForTeam(playerStats: unknown[], teamName: string, field: string): number {
  let sum = 0
  for (const raw of playerStats ?? []) {
    const ps = raw as Record<string, unknown> | null
    if (!ps || String(ps.team_name ?? '') !== teamName) continue
    sum += Number(ps[field] ?? 0)
  }
  return sum
}

/** Team TDs in one game — never sum rec_td (already counted on QB pass_td). */
function teamTouchdownsInGame(
  teamStats: Record<string, number>,
  playerStats: unknown[],
  teamName: string,
  pointsScored: number,
): number {
  const fromTeam = Number(teamStats?.touchdowns)
  if (Number.isFinite(fromTeam) && fromTeam > 0) return fromTeam

  const passTd = sumPlayerStatForTeam(playerStats, teamName, 'pass_td')
  const rushTd = sumPlayerStatForTeam(playerStats, teamName, 'rush_td')
  const fromPlayers = passTd + rushTd
  if (fromPlayers > 0) return fromPlayers

  return Math.max(0, Math.floor(pointsScored / 6))
}

function buildRecapHeadline(args: {
  userDisplay: string
  oppDisplay: string
  userScore: number
  oppScore: number
  won: boolean
  ot: boolean
}): string {
  const { userDisplay, oppDisplay, userScore, oppScore, won, ot } = args
  const margin = Math.abs(userScore - oppScore)
  const otNote = ot ? ' in overtime' : ''

  if (won) {
    if (margin >= 28) return `${userDisplay} rolls past ${oppDisplay}, ${userScore}–${oppScore}${otNote}.`
    if (margin >= 14) return `${userDisplay} pulls away from ${oppDisplay}, ${userScore}–${oppScore}${otNote}.`
    if (margin <= 7) return `${userDisplay} holds off ${oppDisplay}, ${userScore}–${oppScore}${otNote}.`
    return `${userDisplay} beats ${oppDisplay}, ${userScore}–${oppScore}${otNote}.`
  }
  if (margin >= 28) return `${userDisplay} routed by ${oppDisplay}, ${userScore}–${oppScore}${otNote}.`
  if (margin <= 7) return `${userDisplay} falls short against ${oppDisplay}, ${userScore}–${oppScore}${otNote}.`
  return `${userDisplay} loses to ${oppDisplay}, ${userScore}–${oppScore}${otNote}.`
}

export function rankForTeam(rows: StandingsRow[], teamName: string): number | null {
  const r = rows.find((x) => x.teamName === teamName)
  return r?.rank ?? null
}

export function buildLastGameRecap(state: any): LastGameRecap | null {
  const userTeam = String(state?.user_team ?? '').trim()
  if (!userTeam) return null
  const currentWeek = Number(state?.current_week ?? 1)
  const weeks = state?.weeks ?? []
  const results = state?.week_results ?? []

  for (let wi = currentWeek - 2; wi >= 0; wi--) {
    const wk = weeks[wi] ?? []
    const wkRes = results[wi] ?? []
    for (let gi = 0; gi < wk.length; gi++) {
      const g = wk[gi]
      if (!g || (g.home !== userTeam && g.away !== userTeam)) continue
      const r = wkRes[gi]
      if (!r?.played) continue
      const homeScore = Number(r.home_score ?? 0)
      const awayScore = Number(r.away_score ?? 0)
      const userHome = g.home === userTeam
      const userScore = userHome ? homeScore : awayScore
      const oppScore = userHome ? awayScore : homeScore
      const opponent = userHome ? String(g.away) : String(g.home)
      const won = userScore >= oppScore
      const ts = (r.team_stats?.[userTeam] ?? {}) as Record<string, number>
      const playerStats = (r.player_stats ?? []) as unknown[]
      let comp = 0
      let att = 0
      for (const raw of playerStats) {
        const ps = raw as Record<string, unknown> | null
        if (!ps || String(ps.team_name ?? '') !== userTeam) continue
        comp += Number(ps.comp ?? 0)
        att += Number(ps.att ?? 0)
      }
      const userRow = findTeam(state, userTeam)
      const oppRow = findTeam(state, opponent)
      const headline = buildRecapHeadline({
        userDisplay: teamDisplayName(userRow, userTeam),
        oppDisplay: teamDisplayName(oppRow, opponent),
        userScore,
        oppScore,
        won,
        ot: Boolean(r.ot),
      })
      const tds = teamTouchdownsInGame(ts, playerStats, userTeam, userScore)
      const interceptions =
        Number(ts.interceptions ?? 0) || sumPlayerStatForTeam(playerStats, userTeam, 'int_thrown')
      const sacks = Number(ts.sacks ?? 0) || sumPlayerStatForTeam(playerStats, userTeam, 'sacks')
      return {
        week: wi + 1,
        opponent,
        userHome,
        userScore,
        oppScore,
        won,
        ot: Boolean(r.ot),
        headline,
        passYds: Number(ts.pass_yards ?? 0),
        rushYds: Number(ts.rush_yards ?? 0),
        tds,
        interceptions,
        sacks,
        compPct: att > 0 ? Math.round((comp / att) * 100) : null,
      }
    }
  }
  return null
}

export function buildSeasonStatStrip(
  state: any,
  userTeam: string,
  classStandings: StandingsRow[],
  statsRow: { pointsFor: number; pointsAgainst: number; games: number; totalYards: number; turnovers: number } | null,
): Array<{ label: string; value: string; sub: string; positive?: boolean; negative?: boolean }> {
  const games = Math.max(1, statsRow?.games ?? 1)
  const ppg = (statsRow?.pointsFor ?? 0) / games
  const papg = (statsRow?.pointsAgainst ?? 0) / games
  const ypg = (statsRow?.totalYards ?? 0) / games
  const cls = findTeam(state, userTeam)?.classification ?? 'class'

  const ppgRank =
    classStandings
      .slice()
      .sort((a, b) => b.ppg - a.ppg)
      .findIndex((r) => r.teamName === userTeam) + 1
  const ypgRank =
    classStandings.length && statsRow
      ? classStandings
          .slice()
          .sort((a, b) => {
            const ay = (a.pointsFor + a.pointsAgainst) / Math.max(1, a.wins + a.losses)
            const by = (b.pointsFor + b.pointsAgainst) / Math.max(1, b.wins + b.losses)
            return by - ay
          })
          .findIndex((r) => r.teamName === userTeam) + 1
      : null
  const defRank =
    classStandings
      .slice()
      .sort((a, b) => {
        const ap = a.pointsAgainst / Math.max(1, a.wins + a.losses)
        const bp = b.pointsAgainst / Math.max(1, b.wins + b.losses)
        return ap - bp
      })
      .findIndex((r) => r.teamName === userTeam) + 1

  let turnoverMargin = 0
  for (const wi of state?.week_results ?? []) {
    for (const g of wi ?? []) {
      if (!g?.played) continue
      const ts = g.team_stats?.[userTeam]
      if (!ts) continue
      turnoverMargin -= Number(ts.turnovers ?? 0)
      const opp = g.home === userTeam ? g.away : g.home
      turnoverMargin += Number(g.team_stats?.[opp]?.turnovers ?? 0)
    }
  }

  return [
    {
      label: 'Pts / Gm',
      value: ppg.toFixed(1),
      sub: ppgRank > 0 ? `${ppgRank}${ordinal(ppgRank)} in ${cls}` : `— in ${cls}`,
      positive: ppg >= 21,
    },
    {
      label: 'Yds / Gm',
      value: String(Math.round(ypg)),
      sub: ypgRank && ypgRank > 0 ? `${ypgRank}${ordinal(ypgRank)} in ${cls}` : 'season total',
    },
    {
      label: 'Pts Allow',
      value: papg.toFixed(1),
      sub: defRank > 0 ? `${defRank}${ordinal(defRank)} in ${cls}` : `— in ${cls}`,
      positive: papg <= 17,
    },
    {
      label: 'Turnover',
      value: turnoverMargin >= 0 ? `+${turnoverMargin}` : String(turnoverMargin),
      sub: 'margin',
      positive: turnoverMargin > 0,
      negative: turnoverMargin < 0,
    },
  ]
}

function ordinal(n: number): string {
  const v = n % 100
  if (v >= 11 && v <= 13) return 'th'
  switch (n % 10) {
    case 1:
      return 'st'
    case 2:
      return 'nd'
    case 3:
      return 'rd'
    default:
      return 'th'
  }
}

export function buildGoalTiles(
  state: any,
  userTeam: string,
  scheduleRows: ScheduleRow[],
  classStandings: StandingsRow[],
): GoalTile[] {
  const goals = state?.season_goals ?? {}
  const winGoal = typeof goals.win_goal === 'number' ? goals.win_goal : null
  const stageGoal = typeof goals.stage_goal === 'string' ? goals.stage_goal.trim() : null
  const st = state?.standings?.[userTeam] ?? {}
  const wins = Number(st.wins ?? 0)
  const losses = Number(st.losses ?? 0)
  const rank = rankForTeam(classStandings, userTeam)
  const regionGames = scheduleRows.filter((r) => r.isRegionGame)
  const regionWins = regionGames.filter((r) => r.played && r.scoreLine.startsWith('W')).length
  const regionPlayed = regionGames.filter((r) => r.played).length

  const tiles: GoalTile[] = []

  if (winGoal != null) {
    const pct = winGoal > 0 ? Math.min(100, Math.round((wins / winGoal) * 100)) : 100
    const onPace = wins >= winGoal || wins >= winGoal - 1
    tiles.push({
      name: 'Win total',
      status: wins >= winGoal ? 'on' : onPace ? 'track' : 'off',
      statusLabel: wins >= winGoal ? 'Met' : onPace ? 'On pace' : 'Off track',
      progressPct: pct,
      description: `${wins} of ${winGoal} wins`,
      sub: `Board expects ${winGoal}+`,
    })
  }

  if (stageGoal && stageGoal !== 'Just to have fun') {
    let status: GoalTile['status'] = 'track'
    let statusLabel = 'In range'
    let desc = stageGoal
    let pct = 50
    if (stageGoal === 'Winning Season') {
      const ok = wins >= losses
      status = ok ? 'on' : wins + 2 >= losses ? 'track' : 'off'
      statusLabel = ok ? 'On pace' : status === 'track' ? 'In range' : 'Off track'
      desc = `${wins}-${losses} record`
      pct = Math.min(100, Math.round((wins / Math.max(1, wins + losses)) * 100))
    } else if (stageGoal === 'Playoffs') {
      const ok = rank != null && rank <= 8
      status = ok ? 'on' : rank != null && rank <= 12 ? 'track' : 'off'
      statusLabel = ok ? 'On pace' : status === 'track' ? 'In range' : 'Off track'
      desc = rank != null ? `#${rank} in class` : `${wins}-${losses}`
      pct = rank != null ? Math.max(10, 100 - (rank - 1) * 8) : 40
    } else {
      desc = `${wins}-${losses} · ${stageGoal}`
      pct = Math.min(100, wins * 12)
    }
    tiles.push({
      name: 'Stage goal',
      status,
      statusLabel,
      progressPct: pct,
      description: desc,
      sub: stageGoal,
    })
  }

  tiles.push({
    name: 'Class rank',
    status: rank != null && rank <= 5 ? 'on' : rank != null && rank <= 10 ? 'track' : 'off',
    statusLabel: rank != null && rank <= 5 ? 'On pace' : rank != null && rank <= 10 ? 'Holding' : 'Climb needed',
    progressPct: rank != null ? Math.max(8, 100 - (rank - 1) * 9) : 20,
    description: rank != null ? `Currently #${rank}` : 'Unranked',
    sub: `Top of ${findTeam(state, userTeam)?.classification ?? 'class'}`,
  })

  tiles.push({
    name: 'Region games',
    status: regionPlayed === 0 ? 'track' : regionWins >= regionPlayed / 2 ? 'on' : 'off',
    statusLabel: regionPlayed === 0 ? 'Pending' : regionWins >= regionPlayed / 2 ? 'On pace' : 'Catch up',
    progressPct: regionPlayed ? Math.round((regionWins / regionPlayed) * 100) : 15,
    description: regionPlayed ? `${regionWins}-${regionPlayed - regionWins} in region` : 'No region results yet',
    sub: `${regionGames.length} region games scheduled`,
  })

  return tiles.slice(0, 4)
}

type InboxEmailRow = {
  id?: string
  subject?: string
  sender_name?: string
  body?: string
  read?: boolean
  resolved?: boolean
  category?: string
  week?: number
  trigger_conditions?: string[]
}

/** Dashboard / list title — prefer sender when subject is the generic filler label. */
export function inboxEmailDisplayTitle(e: InboxEmailRow): string {
  const subject = String(e.subject ?? '').trim()
  const sender = String(e.sender_name ?? '').trim()
  if ((!subject || subject === 'Quick note') && sender) return sender
  return subject || sender || 'Coach message'
}

function inboxDashboardSubline(e: InboxEmailRow): string {
  const subject = String(e.subject ?? '').trim()
  const sender = String(e.sender_name ?? '').trim()
  const body = String(e.body ?? '').slice(0, 120)
  if (subject && subject !== 'Quick note' && subject !== sender) return subject
  return body
}

/** Newest / most actionable mail first (same week: later entries beat starter pack). */
export function sortInboxEmailsForDisplay(emails: InboxEmailRow[]): InboxEmailRow[] {
  const indexed = emails.map((e, idx) => ({ e, idx }))
  indexed.sort((a, b) => {
    const doneA = a.e.resolved && a.e.read ? 1 : 0
    const doneB = b.e.resolved && b.e.read ? 1 : 0
    if (doneA !== doneB) return doneA - doneB
    const unreadA = a.e.read ? 1 : 0
    const unreadB = b.e.read ? 1 : 0
    if (unreadA !== unreadB) return unreadA - unreadB
    const weekDiff = Number(b.e.week ?? 0) - Number(a.e.week ?? 0)
    if (weekDiff !== 0) return weekDiff
    const checklistA = (a.e.trigger_conditions ?? []).some((t) => String(t) === 'weekly_checklist') ? 1 : 0
    const checklistB = (b.e.trigger_conditions ?? []).some((t) => String(t) === 'weekly_checklist') ? 1 : 0
    if (checklistA !== checklistB) return checklistB - checklistA
    const starterA = (a.e.trigger_conditions ?? []).some((t) => String(t).includes('starter')) ? 1 : 0
    const starterB = (b.e.trigger_conditions ?? []).some((t) => String(t).includes('starter')) ? 1 : 0
    if (starterA !== starterB) return starterA - starterB
    return b.idx - a.idx
  })
  return indexed.map(({ e }) => e)
}

function isStarterInboxEmail(e: InboxEmailRow): boolean {
  return (e.trigger_conditions ?? []).some((t) => String(t).includes('starter'))
}

export function buildInboxPreview(state: any, limit = 5): InboxPreviewItem[] {
  const emails = (state?.coach_inbox?.emails ?? []) as InboxEmailRow[]
  const currentWeek = Number(state?.current_week ?? 1)
  const sorted = sortInboxEmailsForDisplay(emails)
  const hasRecentWeeklyMail = sorted.some((e) => {
    const w = Number(e.week ?? 0)
    return w >= currentWeek - 1 && !isStarterInboxEmail(e)
  })
  const pool = hasRecentWeeklyMail ? sorted.filter((e) => !isStarterInboxEmail(e)) : sorted
  return pool.slice(0, limit).map((e, i) => {
    const read = Boolean(e.read)
    const resolved = Boolean(e.resolved)
    let urgency: InboxPreviewItem['urgency'] = 'info'
    if (resolved && read) urgency = 'done'
    else if (!read && (e.category === 'performance' || e.category === 'admin')) urgency = 'now'
    else if (!read) urgency = 'soon'
    const linkLabel =
      e.category === 'performance'
        ? 'Open gameplan →'
        : e.category === 'player_issue'
          ? 'Edit depth chart →'
          : e.category === 'recruiting'
            ? 'View recruiting →'
            : 'Open inbox →'
    return {
      id: String(e.id ?? `inbox-${i}`),
      title: String(e.sender_name ?? '').trim() || inboxEmailDisplayTitle(e),
      sub: inboxDashboardSubline(e),
      linkLabel,
      urgency,
      week: Number(e.week ?? 0),
    }
  })
}

export function mapNewsArticles(articles: NewsArticle[], limit = 5): TaggedNewsRow[] {
  return articles.slice(0, limit).map((a) => {
    let tag = 'NEWS'
    let tagClass = 'tag-score'
    if (a.type === 'injury') {
      tag = 'INJURY'
      tagClass = 'tag-injury'
    } else if (a.type === 'ranking') {
      tag = 'RANKINGS'
      tagClass = 'tag-rank'
    } else if (a.type === 'recruiting') {
      tag = 'COMMIT'
      tagClass = 'tag-commit'
    } else if (a.type === 'recap') {
      tag = 'SCORES'
      tagClass = 'tag-score'
    } else if (/transfer/i.test(a.title + a.summary)) {
      tag = 'TRANSFER'
      tagClass = 'tag-transfer'
    }
    return { id: a.id, tag, tagClass, headline: a.title }
  })
}

export function buildOpponentScoutSummary(state: any, opponent: string) {
  const bundle = buildScoutingReportBundle(state, opponent)
  if (!bundle) return null
  const off = bundle.offense
  const def = bundle.defense
  const weakness = off.weaknesses?.[0] ?? def.weaknesses?.[0] ?? '—'
  const stopLine = off.whoToStop?.[0] ?? def.whoToAvoid?.[0]
  const watch = stopLine
    ? `${stopLine.player}${stopLine.reason ? ` · ${stopLine.reason}` : ''}`
    : off.keyPlayers?.[0]?.name ?? '—'
  return {
    offense: `${off.identity?.offensiveStyle ?? 'Balanced'} · ${off.runPass?.runPct ?? 50}% run`,
    defense: `${def.identity?.playbook ?? 'Base'} · ${def.identity?.defensiveStyle ?? 'Balanced'}`,
    weakness,
    watch,
  }
}

export function parseScoreLine(scoreLine: string): { outcome: 'W' | 'L' | null; userScore: number; oppScore: number } {
  const m = scoreLine.match(/^([WL])\s*(?:\(OT\)\s*)?(\d+)-(\d+)/)
  if (!m) return { outcome: null, userScore: 0, oppScore: 0 }
  return { outcome: m[1] as 'W' | 'L', userScore: Number(m[2]), oppScore: Number(m[3]) }
}
