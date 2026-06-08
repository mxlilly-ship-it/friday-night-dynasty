/** Postseason tier for a team (matches backend `_postseason_tier_for_team`). */
export type PostseasonTier = 'champion' | 'championship' | 'semifinal' | 'playoffs' | 'none'

const ROUND_RANK: Record<string, number> = {
  Championship: 3,
  Semifinal: 2,
  Quarterfinal: 1,
}

export function postseasonTierForTeam(
  teamName: string,
  bracketResults: Array<{ round?: string; home?: string; away?: string }>,
  champion: string,
): PostseasonTier {
  const tn = String(teamName || '').trim()
  if (!tn) return 'none'
  if (tn === String(champion || '').trim()) return 'champion'
  let best = 0
  let made = false
  for (const g of bracketResults || []) {
    if (!g || typeof g !== 'object') continue
    if (g.home !== tn && g.away !== tn) continue
    made = true
    const rnd = String(g.round || '')
    best = Math.max(best, ROUND_RANK[rnd] ?? 0)
  }
  if (best >= 3) return 'championship'
  if (best >= 2) return 'semifinal'
  if (made) return 'playoffs'
  return 'none'
}

const TIER_RANK: Record<PostseasonTier, number> = {
  none: 0,
  playoffs: 1,
  semifinal: 2,
  championship: 3,
  champion: 4,
}

export type GoalEvaluation = {
  winGoal: number | null
  stageGoal: string | null
  wins: number
  losses: number
  winMet: boolean | null
  stageMet: boolean | null
  postseasonTier: PostseasonTier
  postseasonLabel: string
}

export function evaluateSeasonGoals(
  wins: number,
  losses: number,
  seasonGoals: { win_goal?: number; stage_goal?: string } | null | undefined,
  postseasonTier: PostseasonTier,
): GoalEvaluation {
  const winGoal =
    seasonGoals && typeof seasonGoals.win_goal === 'number' && Number.isFinite(seasonGoals.win_goal)
      ? seasonGoals.win_goal
      : null
  const stageGoal =
    seasonGoals && typeof seasonGoals.stage_goal === 'string' ? seasonGoals.stage_goal.trim() || null : null

  let winMet: boolean | null = null
  if (winGoal != null) winMet = wins >= winGoal

  const achievedRank = TIER_RANK[postseasonTier] ?? 0
  let stageMet: boolean | null = null
  if (stageGoal === 'Just to have fun') {
    stageMet = true
  } else if (stageGoal) {
    let goalRank: number | null = null
    if (stageGoal === 'Winning Season') goalRank = wins >= losses ? 0 : 999
    else if (stageGoal === 'Playoffs') goalRank = 1
    else if (stageGoal === 'Semifinal') goalRank = 2
    else if (stageGoal === 'State Championship') goalRank = 3
    else if (stageGoal === 'Title Winner') goalRank = 4
    if (goalRank != null) {
      if (goalRank === 999) stageMet = false
      else stageMet = achievedRank >= goalRank
    }
  }

  const postseasonLabel =
    postseasonTier === 'champion'
      ? 'State champion'
      : postseasonTier === 'championship'
        ? 'Championship game'
        : postseasonTier === 'semifinal'
          ? 'Semifinals'
          : postseasonTier === 'playoffs'
            ? 'Playoffs'
            : 'Did not qualify'

  return {
    winGoal,
    stageGoal,
    wins,
    losses,
    winMet,
    stageMet,
    postseasonTier,
    postseasonLabel,
  }
}
