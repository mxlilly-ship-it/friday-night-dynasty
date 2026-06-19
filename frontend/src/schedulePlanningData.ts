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
