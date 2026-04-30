/**
 * Region labels are free-form strings on teams; these are common presets for editors/UI.
 * Must match the string on each team and in league_structure.class_region_bounds keys exactly.
 */

/** North / East / South / West */
export const REGION_PRESET_COMPASS = ['North', 'East', 'South', 'West'] as const

/** A / B / C / D */
export const REGION_PRESET_LETTERS = ['A', 'B', 'C', 'D'] as const

/** Region 1 … Region 4 */
export const REGION_PRESET_NUMBERED = ['Region 1', 'Region 2', 'Region 3', 'Region 4'] as const

/** Short numeric labels "1" … "4" */
export const REGION_PRESET_NUMBERED_SHORT = ['1', '2', '3', '4'] as const

export const REGION_NAME_PRESETS: Record<
  string,
  readonly string[]
> = {
  compass: REGION_PRESET_COMPASS,
  letters: REGION_PRESET_LETTERS,
  numbered: REGION_PRESET_NUMBERED,
  numbered_short: REGION_PRESET_NUMBERED_SHORT,
}

/** Typical targets for schools per region when designing a league (not enforced unless bounds are set). 8 = 32÷4; 10 = 40÷4. */
export const SUGGESTED_TEAMS_PER_REGION = [5, 6, 8, 10, 12] as const

/** Total teams in one classification with four equal regions (editors / UI). 32 → 4×8; 40 → 4×10. */
export const SUGGESTED_CLASS_TOTAL_SIZES = [32, 40] as const
