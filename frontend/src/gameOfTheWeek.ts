/** Pick one marquee matchup per regular-season week for the league schedule. */

export type GameOfTheWeekPick = {
  week: number
  gameIndex: number
  home: string
  away: string
}

function findTeam(state: any, teamName: string) {
  return (state?.teams ?? []).find((t: { name?: string }) => t?.name === teamName) ?? null
}

function teamPrestige(state: any, teamName: string): number {
  const t = findTeam(state, teamName)
  const p = Number(t?.prestige)
  return Number.isFinite(p) ? p : 5
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
  if (!a || !b || a === b) return false
  const ta = findTeam(state, a)
  const tb = findTeam(state, b)
  const aRivals = parseRivals(ta)
  const bRivals = parseRivals(tb)
  return aRivals.includes(b) || bRivals.includes(a)
}

/** Wins for `teamName` in weeks strictly before `week1Based`. */
function winsBeforeWeek(state: any, teamName: string, week1Based: number): number {
  const weeks = state?.weeks ?? []
  const results = state?.week_results ?? []
  let wins = 0
  const limit = Math.max(0, week1Based - 1)
  for (let wi = 0; wi < limit && wi < weeks.length; wi++) {
    const weekGames = weeks[wi] ?? []
    const weekRes = results[wi] ?? []
    for (let gi = 0; gi < weekGames.length; gi++) {
      const g = weekGames[gi]
      const r = weekRes[gi]
      if (!g || !r?.played) continue
      const home = String(g.home ?? '')
      const away = String(g.away ?? '')
      if (home !== teamName && away !== teamName) continue
      const hs = Number(r.home_score ?? 0)
      const as = Number(r.away_score ?? 0)
      const userHome = home === teamName
      const userScore = userHome ? hs : as
      const oppScore = userHome ? as : hs
      if (userScore >= oppScore) wins++
    }
  }
  return wins
}

function marqueeScore(state: any, home: string, away: string, week1Based: number): number {
  const pHome = teamPrestige(state, home)
  const pAway = teamPrestige(state, away)
  let score = pHome + pAway

  if (pHome >= 12 && pAway >= 12) score += 10
  if (Math.min(pHome, pAway) >= 10) score += 4
  if (areRivals(state, home, away)) score += 14

  const wHome = winsBeforeWeek(state, home, week1Based)
  const wAway = winsBeforeWeek(state, away, week1Based)
  score += (wHome + wAway) * 1.5

  // Unbeaten clash bonus entering the week
  const gamesBefore = Math.max(0, week1Based - 1)
  if (gamesBefore > 0 && wHome === gamesBefore && wAway === gamesBefore) score += 8

  return score
}

function tieBreakKey(home: string, away: string, gameIndex: number): string {
  return `${home}\0${away}\0${gameIndex}`
}

export function pickGameOfTheWeekForWeek(state: any, week1Based: number): GameOfTheWeekPick | null {
  const weeks = state?.weeks ?? []
  const wi = week1Based - 1
  if (wi < 0 || wi >= weeks.length) return null
  const weekGames = weeks[wi] ?? []
  if (!weekGames.length) return null

  let best: GameOfTheWeekPick | null = null
  let bestScore = -Infinity
  let bestKey = ''

  for (let gi = 0; gi < weekGames.length; gi++) {
    const g = weekGames[gi]
    if (!g) continue
    const home = String(g.home ?? '').trim()
    const away = String(g.away ?? '').trim()
    if (!home || !away) continue
    const score = marqueeScore(state, home, away, week1Based)
    const key = tieBreakKey(home, away, gi)
    if (score > bestScore || (score === bestScore && key < bestKey)) {
      bestScore = score
      bestKey = key
      best = { week: week1Based, gameIndex: gi, home, away }
    }
  }

  return best
}

export function isGameOfTheWeek(state: any, week1Based: number, gameIndex: number): boolean {
  const pick = pickGameOfTheWeekForWeek(state, week1Based)
  return pick != null && pick.gameIndex === gameIndex
}

export function gameOfTheWeekLabel(pick: GameOfTheWeekPick | null): string {
  if (!pick) return ''
  return `${pick.home} vs ${pick.away}`
}
