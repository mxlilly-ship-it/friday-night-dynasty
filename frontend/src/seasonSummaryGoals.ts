import { ARCHIVE_PLAYOFF_ROUND_PRIORITY, partitionBracketGamesByConnectedTeams } from './leagueHistoryView'

/** Postseason tier for a team (matches backend `_postseason_tier_for_team`). */
export type PostseasonTier = 'champion' | 'championship' | 'semifinal' | 'playoffs' | 'none'

const CHAMP_ROUND_VALUE = ARCHIVE_PLAYOFF_ROUND_PRIORITY.Championship ?? 6
const SEMI_ROUND_VALUE = ARCHIVE_PLAYOFF_ROUND_PRIORITY.Semifinal ?? 5

export type BracketGame = { round?: string; home?: string; away?: string }

function resolveBracketClassKey(
  bc: Record<string, unknown> | undefined | null,
  preferred: string | null | undefined,
): string | null {
  if (!bc || typeof bc !== 'object') return null
  const keys = Object.keys(bc)
  if (!keys.length) return null
  const w = String(preferred ?? '').trim()
  if (!w) return null
  if (Object.prototype.hasOwnProperty.call(bc, w)) return w
  const lower = w.toLowerCase()
  return keys.find((k) => k.toLowerCase() === lower) ?? null
}

function userClassificationFromState(saveState: unknown, userTeam: string): string {
  const ut = userTeam.trim()
  const state = saveState as {
    playoffs?: { user_class?: string }
    teams?: Array<{ name?: string; classification?: string }>
  } | null
  const fromPlayoffs = String(state?.playoffs?.user_class ?? '').trim()
  if (fromPlayoffs) return fromPlayoffs
  const row = (state?.teams ?? []).find((t) => t?.name === ut)
  const c = row?.classification
  return c != null && String(c).trim() !== '' ? String(c).trim() : ''
}

/**
 * Bracket games + class champion for goal/tier evaluation — always the user's classification,
 * not the bracket dropdown view (which may show another class).
 */
export function resolveSeasonSummaryPostseasonContext(
  saveState: unknown,
  archived: Record<string, unknown> | null | undefined,
  userTeam: string,
): { bracketResults: BracketGame[]; champion: string } {
  const ut = String(userTeam || '').trim()
  const userClass = userClassificationFromState(saveState, ut)
  const games: BracketGame[] = []
  let champion = ''

  const pbc = archived?.playoffs_by_class as
    | Record<string, { bracket_results?: BracketGame[]; champion?: string }>
    | undefined
  const liveBc = (saveState as { playoffs?: { by_class?: Record<string, { bracket_results?: BracketGame[]; champion?: string }> } })
    ?.playoffs?.by_class
  const bcKeys = pbc && Object.keys(pbc).length ? pbc : liveBc
  const classKey = resolveBracketClassKey(bcKeys as Record<string, unknown> | undefined, userClass)

  const applyInner = (
    inner: { bracket_results?: BracketGame[]; champion?: string } | undefined,
    fallbackChamp?: string,
  ) => {
    if (!inner) return
    if (Array.isArray(inner.bracket_results) && inner.bracket_results.length) {
      games.length = 0
      games.push(...inner.bracket_results)
    }
    const ch = String(inner.champion ?? fallbackChamp ?? '').trim()
    if (ch) champion = ch
  }

  if (classKey && pbc?.[classKey]) {
    applyInner(pbc[classKey], String(archived?.state_champion ?? ''))
  }
  if (!games.length && classKey && liveBc?.[classKey]) {
    applyInner(liveBc[classKey], String((saveState as { playoffs?: { champion?: string } })?.playoffs?.champion ?? ''))
  }

  if (!games.length) {
    const legacyArchived = (archived?.playoffs as { bracket_results?: BracketGame[] } | undefined)?.bracket_results
    if (Array.isArray(legacyArchived) && legacyArchived.length) games.push(...legacyArchived)
  }

  if (!games.length && liveBc) {
    for (const sub of Object.values(liveBc)) {
      if (Array.isArray(sub?.bracket_results)) games.push(...sub.bracket_results)
    }
  }

  if (!games.length) {
    const flat = (saveState as { playoffs?: { bracket_results?: BracketGame[] } })?.playoffs?.bracket_results
    if (Array.isArray(flat)) games.push(...flat)
  }

  if (ut && games.length && !games.some((g) => g.home === ut || g.away === ut)) {
    const parts = partitionBracketGamesByConnectedTeams(games) as BracketGame[][]
    const userPart = parts.find((comp) => comp.some((g) => g.home === ut || g.away === ut))
    if (userPart?.length) {
      games.length = 0
      games.push(...userPart)
    }
  }

  if (!champion) {
    if (classKey && pbc?.[classKey]?.champion) champion = String(pbc[classKey].champion)
    else if (classKey && liveBc?.[classKey]?.champion) champion = String(liveBc[classKey].champion)
    else if (pbc && ut) {
      for (const inner of Object.values(pbc)) {
        if (inner?.champion === ut) {
          champion = ut
          break
        }
      }
    }
  }
  if (!champion) {
    champion = String(
      archived?.state_champion ?? (saveState as { playoffs?: { champion?: string } })?.playoffs?.champion ?? '',
    )
  }

  return { bracketResults: games, champion }
}

export function postseasonTierForTeam(
  teamName: string,
  bracketResults: BracketGame[],
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
    best = Math.max(best, ARCHIVE_PLAYOFF_ROUND_PRIORITY[rnd] ?? 0)
  }
  if (best >= CHAMP_ROUND_VALUE) return 'championship'
  if (best >= SEMI_ROUND_VALUE) return 'semifinal'
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
