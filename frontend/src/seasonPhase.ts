import { findSeasonEntryByCalendarYear } from './leagueHistoryView'

/** Align UI phase with save (matches TeamHomePage). */
export function deriveUiPhaseFromSave(
  saveState: any,
  leagueHistory?: { seasons?: unknown[] } | null,
): string {
  if (!saveState) return 'regular'
  const raw = String(saveState.season_phase ?? '').toLowerCase()
  if (
    raw === 'playoffs' ||
    raw === 'season_summary' ||
    raw === 'schedule_planning' ||
    raw === 'offseason' ||
    raw === 'done'
  ) {
    if (raw === 'playoffs') {
      const p = saveState?.playoffs
      if (p?.completed) {
        const cy = Number(saveState?.current_year)
        const seasons = Array.isArray(leagueHistory?.seasons) ? leagueHistory.seasons : []
        if (Number.isFinite(cy) && seasons.some((s) => Number((s as { year?: number })?.year) === cy)) {
          return 'season_summary'
        }
      }
    }
    return raw
  }
  const stages = saveState.preseason_stages
  const idx = Number(saveState.preseason_stage_index ?? 0)
  if (Array.isArray(stages) && stages.length > 0 && idx >= stages.length) return 'regular'
  if (raw === 'preseason') return 'preseason'
  if (Array.isArray(stages) && stages.length > 0 && idx < stages.length) return 'preseason'
  return 'regular'
}

/** True when Continue from season summary should begin offseason / schedule planning. */
export function shouldBeginOffseason(saveState: any, uiPhase: string): boolean {
  if (uiPhase === 'season_summary') return true
  const raw = String(saveState?.season_phase ?? '').toLowerCase()
  return raw === 'season_summary'
}

/** True when the user should pick cross-region opponents before continuing. */
export function saveNeedsSchedulePlanning(saveState: any): boolean {
  const raw = saveState?.schedule_planning_info
  if (!raw || typeof raw !== 'object') return false
  const slots = Array.isArray(raw.slots) ? raw.slots : []
  return slots.length > 0
}

export function seasonYearFromSave(saveState: any): number | null {
  const cy = Number(saveState?.current_year)
  return Number.isFinite(cy) ? cy : null
}

export function leagueHistoryHasSeasonYear(
  leagueHistory: { seasons?: unknown[] } | null | undefined,
  year: number | null,
): boolean {
  if (year == null) return false
  const seasons = Array.isArray(leagueHistory?.seasons) ? leagueHistory.seasons : []
  return Boolean(findSeasonEntryByCalendarYear(seasons, year))
}
