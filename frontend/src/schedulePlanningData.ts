export type SchedulePlanningSlot = {
  slot_index: number
  label: string
  opponent_region: string
  eligible_teams: string[]
}

export type SchedulePlanningInfo = {
  slot_count: number
  in_region_games: number
  total_games: number
  slots: SchedulePlanningSlot[]
}

export type CrossRegionSlotSelection = {
  opponent: string
  userHome: boolean
}

export type CrossRegionSelections = Record<number, CrossRegionSlotSelection>

export function defaultUserHomeForSlot(slotIndex: number): boolean {
  return slotIndex % 2 === 0
}

export function emptySlotSelection(slotIndex: number): CrossRegionSlotSelection {
  return { opponent: '', userHome: defaultUserHomeForSlot(slotIndex) }
}

export function schedulePlanningInfoFromState(saveState: any): SchedulePlanningInfo | null {
  const raw = saveState?.schedule_planning_info
  if (!raw || typeof raw !== 'object') return null
  const slots = Array.isArray(raw.slots) ? raw.slots : []
  if (slots.length < 1) return null
  return {
    slot_count: Number(raw.slot_count ?? slots.length),
    in_region_games: Number(raw.in_region_games ?? 9),
    total_games: Number(raw.total_games ?? slots.length + 9),
    slots: slots.map((s: any) => ({
      slot_index: Number(s.slot_index ?? 0),
      label: String(s.label ?? 'Out-of-region'),
      opponent_region: String(s.opponent_region ?? ''),
      eligible_teams: Array.isArray(s.eligible_teams) ? s.eligible_teams.map(String) : [],
    })),
  }
}

export function buildCrossRegionPicksPayload(
  info: SchedulePlanningInfo,
  selections: CrossRegionSelections,
): { slot_index: number; opponent: string; user_home: boolean }[] {
  return info.slots.map((slot) => {
    const sel = selections[slot.slot_index] ?? emptySlotSelection(slot.slot_index)
    return {
      slot_index: slot.slot_index,
      opponent: String(sel.opponent ?? '').trim(),
      user_home: Boolean(sel.userHome),
    }
  })
}

/** WV classes that use cross-region templates (3A pod-only leagues skip this step). */
export function userClassExpectsCrossRegionPicks(saveState: any): boolean {
  const userTeam = String(saveState?.user_team ?? '').trim()
  if (!userTeam) return false
  const teams = Array.isArray(saveState?.teams) ? saveState.teams : []
  const row = teams.find((t: { name?: string }) => String(t?.name ?? '') === userTeam)
  const cls = String(row?.classification ?? '')
    .trim()
    .toUpperCase()
  return cls === '1A' || cls === '2A' || cls === '4A'
}

/** How many out-of-region games the user's class requires (0 = skip straight to offseason). */
export function crossRegionSlotCountFromSave(saveState: any): number {
  const n = Number(saveState?.user_cross_region_slot_count)
  if (Number.isFinite(n) && n >= 0) return n
  const info = schedulePlanningInfoFromState(saveState)
  return info?.slot_count ?? 0
}

export function allSlotsFilled(info: SchedulePlanningInfo, selections: CrossRegionSelections): boolean {
  return info.slots.every((s) => Boolean(String(selections[s.slot_index]?.opponent ?? '').trim()))
}

/** Restore UI selections from per-team picks stored on the league save. */
export function crossRegionSelectionsFromSaved(
  saveState: any,
  userTeam: string,
  info: SchedulePlanningInfo | null,
): CrossRegionSelections {
  if (!info || !userTeam) return {}
  const raw = saveState?.cross_region_picks
  const userPicks = raw && typeof raw === 'object' ? raw[userTeam] : null
  if (!userPicks || typeof userPicks !== 'object') return {}
  const out: CrossRegionSelections = {}
  for (const slot of info.slots) {
    const rawSlot = userPicks[slot.slot_index] ?? userPicks[String(slot.slot_index)]
    if (!rawSlot || typeof rawSlot !== 'object') continue
    const opp = String((rawSlot as { opponent?: string }).opponent ?? '').trim()
    if (!opp) continue
    const uh = (rawSlot as { user_home?: boolean }).user_home
    out[slot.slot_index] = {
      opponent: opp,
      userHome: uh != null ? Boolean(uh) : defaultUserHomeForSlot(slot.slot_index),
    }
  }
  return out
}

/** True once any regular-season week result slot is marked played. */
export function saveHasPlayedRegularSeasonGames(saveState: any): boolean {
  const weeks = saveState?.week_results
  if (!Array.isArray(weeks)) return false
  for (const wk of weeks) {
    if (!Array.isArray(wk)) continue
    for (const g of wk) {
      if (g && typeof g === 'object' && g.played) return true
    }
  }
  return false
}

/** True for shared online leagues (opening schedule is auto-built, not per-coach). */
export function isMultiplayerLeagueSave(saveState: any): boolean {
  if (!saveState || typeof saveState !== 'object') return false
  if (saveState.multiplayer_league) return true
  const mp = saveState.multiplayer
  return Boolean(mp && typeof mp === 'object' && (mp.league_id || mp.multiplayer_league))
}

/** Dynasty start: schedule planning before the first regular-season game. */
export function isInitialDynastySchedulePlanning(saveState: any, phase: string): boolean {
  // Multiplayer leagues never use the single-player opening schedule picker.
  if (isMultiplayerLeagueSave(saveState)) return false
  if (String(phase || '').trim().toLowerCase() !== 'schedule_planning') return false
  if (saveState?.cross_region_picks) return false
  return !saveHasPlayedRegularSeasonGames(saveState)
}
