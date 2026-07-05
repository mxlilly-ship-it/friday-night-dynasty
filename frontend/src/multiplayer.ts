export type LeagueListTeam = {
  team_name: string | null
  status: string
  control_mode: string
  role: string
  coach_setup_complete?: boolean
}
export type LeagueListItem = {
  league_id: string
  name: string
  status: string
  is_commissioner: boolean
  is_platform_owner_view?: boolean
  can_run_league?: boolean
  teams: LeagueListTeam[]
  updated_at: number
  badges?: string[]
  submitted?: boolean
  your_turn?: boolean
  week_label?: string | null
}

export type LeagueDashboardData = {
  league_id: string
  league_name: string
  league_crest: string
  league_subtitle: string
  week_label: string
  season_phase: string
  stage_key: string
  countdown_label: string | null
  countdown_value: string | null
  progress: { submitted: number; total: number; percent: number }
  your_status: { submitted: boolean; can_unsubmit?: boolean; label: string; sub_label: string }
  division_submissions: Array<{
    division: string
    submitted_count: number
    total_count: number
    teams: Array<{ name: string; submitted: boolean; is_human: boolean }>
  }>
  featured_game: {
    week: number
    your_team: string
    opponent: string
    is_home: boolean
    your_record: string
    opponent_record: string
    your_initials: string
    opponent_initials: string
    division: string
    tags: string[]
  } | null
  slate_games: Array<{
    home: string
    away: string
    home_initials: string
    away_initials: string
    division: string
    notable: boolean
    tags: string[]
  }>
  standings_by_division: Array<{
    division: string
    rows: Array<{ rank: number; team: string; record: string; is_you: boolean }>
  }>
  full_league_standings: Array<{
    rank: number
    team: string
    record: string
    division: string
    is_you: boolean
  }>
  activity: Array<{ icon: string; text: string; time_label: string; created_at?: number }>
  chat_enabled: boolean
  chat_messages?: LeagueChatMessage[]
  is_commissioner: boolean
  is_read_only_admin: boolean
  can_run_league?: boolean
  acting_team_name: string | null
  state_version: number
}

export type LeagueChatMessage = {
  id: string
  user_id: string
  team_name: string | null
  display_name: string
  body: string
  created_at: number
  time_label: string
  is_you?: boolean
}

export type LeagueMineResponse = {
  leagues: LeagueListItem[]
  is_platform_owner: boolean
  platform_owner_configured?: boolean
  account_email?: string
}

export type CommishMember = {
  user_id: string
  email: string
  team_name: string | null
  role: string
  status: string
  control_mode: string
  coach_setup_complete: boolean
  submitted: boolean
}

export type CommishPendingInvite = {
  invite_id: string
  email: string
  status: string
  created_at: number
}

export type CommishDashboardData = {
  league_id: string
  league_name: string
  week_label: string
  season_phase: string
  stage_key: string
  progress: { submitted: number; total: number; percent: number }
  settings: {
    advance_mode: string
    advance_deadline_dow: number | null
    advance_deadline_time_local: string
    submit_lockout_minutes: number
    timezone: string
    advance_deadline_iso: string | null
    countdown_value: string | null
  }
  members: CommishMember[]
  pending_invites: CommishPendingInvite[]
  vacant_teams: string[]
  all_teams: string[]
  state_version: number
  is_read_only_admin?: boolean
  can_manage?: boolean
  acting_team_name?: string | null
  coach_setup_complete?: boolean
  your_status?: { submitted: boolean; can_unsubmit?: boolean; label: string; sub_label: string }
}

export type AssignTeamResult = {
  team_name: string
  pin: string
  user_id?: string
}

export async function fetchMyLeagues(
  apiBase: string,
  headers: Record<string, string>,
): Promise<LeagueMineResponse> {
  const r = await fetch(`${apiBase}/leagues/mine`, { headers })
  if (!r.ok) throw new Error(await r.text())
  const data = (await r.json()) as LeagueMineResponse
  return {
    leagues: data.leagues ?? [],
    is_platform_owner: Boolean(data.is_platform_owner),
    platform_owner_configured: Boolean(data.platform_owner_configured),
    account_email: data.account_email ? String(data.account_email) : '',
  }
}

export async function fetchLeagueDashboard(
  apiBase: string,
  headers: Record<string, string>,
  leagueId: string,
  teamName?: string,
): Promise<LeagueDashboardData> {
  const q = teamName ? `?team_name=${encodeURIComponent(teamName)}` : ''
  const r = await fetch(`${apiBase}/leagues/${leagueId}/dashboard${q}`, { headers })
  if (!r.ok) throw new Error(await r.text())
  return (await r.json()) as LeagueDashboardData
}

export async function submitLeagueWeek(
  apiBase: string,
  headers: Record<string, string>,
  leagueId: string,
  teamName: string,
): Promise<void> {
  const q = `?team_name=${encodeURIComponent(teamName)}`
  const r = await fetch(`${apiBase}/leagues/${leagueId}/submit${q}`, {
    method: 'POST',
    headers: { ...headers, 'Content-Type': 'application/json' },
  })
  if (!r.ok) throw new Error(await r.text())
}

export async function unsubmitLeagueWeek(
  apiBase: string,
  headers: Record<string, string>,
  leagueId: string,
  teamName: string,
): Promise<void> {
  const q = `?team_name=${encodeURIComponent(teamName)}`
  const r = await fetch(`${apiBase}/leagues/${leagueId}/submit${q}`, {
    method: 'DELETE',
    headers: { ...headers, 'Content-Type': 'application/json' },
  })
  if (!r.ok) throw new Error(await r.text())
}

export async function verifyTeamPin(
  apiBase: string,
  headers: Record<string, string>,
  leagueId: string,
  teamName: string,
  pin: string,
): Promise<boolean> {
  const r = await fetch(`${apiBase}/leagues/${leagueId}/teams/${encodeURIComponent(teamName)}/verify-pin`, {
    method: 'POST',
    headers: { ...headers, 'Content-Type': 'application/json' },
    body: JSON.stringify({ pin }),
  })
  return r.ok
}

export type LeagueGameBundle = {
  league_id: string
  team_name: string
  state: Record<string, unknown>
  league_history: { seasons?: unknown[] }
  records: Record<string, unknown>
  state_version: number
}

export async function fetchLeagueGame(
  apiBase: string,
  headers: Record<string, string>,
  leagueId: string,
  teamName: string,
): Promise<LeagueGameBundle> {
  const q = `?team_name=${encodeURIComponent(teamName)}`
  const r = await fetch(`${apiBase}/leagues/${leagueId}/game${q}`, { headers })
  if (!r.ok) throw new Error(await r.text())
  return (await r.json()) as LeagueGameBundle
}

export async function saveLeagueGame(
  apiBase: string,
  headers: Record<string, string>,
  leagueId: string,
  teamName: string,
  state: Record<string, unknown>,
): Promise<void> {
  const q = `?team_name=${encodeURIComponent(teamName)}`
  const r = await fetch(`${apiBase}/leagues/${leagueId}/game${q}`, {
    method: 'PUT',
    headers: { ...headers, 'Content-Type': 'application/json' },
    body: JSON.stringify({ state }),
  })
  if (!r.ok) throw new Error(await r.text())
}

export async function fetchLeagueCommishGame(
  apiBase: string,
  headers: Record<string, string>,
  leagueId: string,
): Promise<LeagueGameBundle> {
  const r = await fetch(`${apiBase}/leagues/${leagueId}/commish/game`, { headers })
  if (!r.ok) throw new Error(await r.text())
  return (await r.json()) as LeagueGameBundle
}

export async function saveLeagueCommishGame(
  apiBase: string,
  headers: Record<string, string>,
  leagueId: string,
  state: Record<string, unknown>,
): Promise<void> {
  const r = await fetch(`${apiBase}/leagues/${leagueId}/commish/game`, {
    method: 'PUT',
    headers: { ...headers, 'Content-Type': 'application/json' },
    body: JSON.stringify({ state }),
  })
  if (!r.ok) throw new Error(await r.text())
}

export async function fetchCommishDashboard(
  apiBase: string,
  headers: Record<string, string>,
  leagueId: string,
): Promise<CommishDashboardData> {
  const r = await fetch(`${apiBase}/leagues/${leagueId}/commish/dashboard`, { headers })
  if (!r.ok) throw new Error(await r.text())
  return (await r.json()) as CommishDashboardData
}

export async function deleteAdminLeague(
  apiBase: string,
  headers: Record<string, string>,
  leagueId: string,
): Promise<{ ok: boolean; league_id: string; name: string; status?: string }> {
  const r = await fetch(`${apiBase}/leagues/admin/leagues/${encodeURIComponent(leagueId)}`, {
    method: 'DELETE',
    headers: { ...headers, 'Content-Type': 'application/json' },
  })
  if (!r.ok) throw new Error(await r.text())
  return (await r.json()) as { ok: boolean; league_id: string; name: string; status?: string }
}

export type DeletedLeagueListItem = {
  league_id: string
  name: string
  status: string
  updated_at: number
  commissioner_user_id?: string
}

export async function fetchDeletedLeagues(
  apiBase: string,
  headers: Record<string, string>,
): Promise<DeletedLeagueListItem[]> {
  const r = await fetch(`${apiBase}/leagues/admin/leagues/deleted`, { headers })
  if (!r.ok) throw new Error(await r.text())
  const data = (await r.json()) as { leagues?: DeletedLeagueListItem[] }
  return data.leagues ?? []
}

export async function restoreAdminLeague(
  apiBase: string,
  headers: Record<string, string>,
  leagueId: string,
): Promise<{ ok: boolean; league_id: string; name: string }> {
  const r = await fetch(
    `${apiBase}/leagues/admin/leagues/${encodeURIComponent(leagueId)}/restore`,
    { method: 'POST', headers: { ...headers, 'Content-Type': 'application/json' } },
  )
  if (!r.ok) throw new Error(await r.text())
  return (await r.json()) as { ok: boolean; league_id: string; name: string }
}

export async function permanentDeleteAdminLeague(
  apiBase: string,
  headers: Record<string, string>,
  leagueId: string,
): Promise<{ ok: boolean; league_id: string; name: string; permanently_deleted?: boolean }> {
  const r = await fetch(
    `${apiBase}/leagues/admin/leagues/${encodeURIComponent(leagueId)}/permanent`,
    { method: 'DELETE', headers: { ...headers, 'Content-Type': 'application/json' } },
  )
  if (!r.ok) throw new Error(await r.text())
  return (await r.json()) as {
    ok: boolean
    league_id: string
    name: string
    permanently_deleted?: boolean
  }
}

export async function inviteToLeague(
  apiBase: string,
  headers: Record<string, string>,
  leagueId: string,
  email: string,
): Promise<{ email_sent?: boolean }> {
  const r = await fetch(`${apiBase}/leagues/${leagueId}/invites`, {
    method: 'POST',
    headers: { ...headers, 'Content-Type': 'application/json' },
    body: JSON.stringify({ email }),
  })
  if (!r.ok) throw new Error(await r.text())
  return (await r.json()) as { email_sent?: boolean }
}

export async function fetchLeagueChat(
  apiBase: string,
  headers: Record<string, string>,
  leagueId: string,
): Promise<LeagueChatMessage[]> {
  const r = await fetch(`${apiBase}/leagues/${leagueId}/chat`, { headers })
  if (!r.ok) throw new Error(await r.text())
  const data = (await r.json()) as { messages?: LeagueChatMessage[] }
  return data.messages ?? []
}

export async function postLeagueChat(
  apiBase: string,
  headers: Record<string, string>,
  leagueId: string,
  body: string,
  teamName?: string | null,
): Promise<LeagueChatMessage> {
  const r = await fetch(`${apiBase}/leagues/${leagueId}/chat`, {
    method: 'POST',
    headers: { ...headers, 'Content-Type': 'application/json' },
    body: JSON.stringify({ body, team_name: teamName || undefined }),
  })
  if (!r.ok) throw new Error(await r.text())
  return (await r.json()) as LeagueChatMessage
}

export async function assignTeamByEmail(
  apiBase: string,
  headers: Record<string, string>,
  leagueId: string,
  email: string,
  teamName: string,
): Promise<AssignTeamResult> {
  const r = await fetch(`${apiBase}/leagues/${leagueId}/members/assign-by-email`, {
    method: 'POST',
    headers: { ...headers, 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, team_name: teamName }),
  })
  if (!r.ok) throw new Error(await r.text())
  return (await r.json()) as AssignTeamResult
}

export async function resetMemberPin(
  apiBase: string,
  headers: Record<string, string>,
  leagueId: string,
  userId: string,
): Promise<AssignTeamResult> {
  const r = await fetch(`${apiBase}/leagues/${leagueId}/members/${encodeURIComponent(userId)}/reset-pin`, {
    method: 'POST',
    headers: { ...headers, 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  })
  if (!r.ok) throw new Error(await r.text())
  return (await r.json()) as AssignTeamResult
}

export type CommishSettingsPatch = {
  advance_mode?: string
  advance_deadline_dow?: number | null
  advance_deadline_time_local?: string
  submit_lockout_minutes?: number
  timezone?: string
}

export async function updateCommishSettings(
  apiBase: string,
  headers: Record<string, string>,
  leagueId: string,
  patch: CommishSettingsPatch,
): Promise<CommishSettingsPatch> {
  const r = await fetch(`${apiBase}/leagues/${leagueId}/commish/settings`, {
    method: 'PATCH',
    headers: { ...headers, 'Content-Type': 'application/json' },
    body: JSON.stringify(patch),
  })
  if (!r.ok) throw new Error(await r.text())
  return (await r.json()) as CommishSettingsPatch
}

export async function commishSimWeek(
  apiBase: string,
  headers: Record<string, string>,
  leagueId: string,
): Promise<{ ok: boolean; message: string; season_phase: string; current_week: number }> {
  const r = await fetch(`${apiBase}/leagues/${leagueId}/commish/sim-week`, {
    method: 'POST',
    headers: { ...headers, 'Content-Type': 'application/json' },
  })
  if (!r.ok) throw new Error(await r.text())
  return (await r.json()) as { ok: boolean; message: string; season_phase: string; current_week: number }
}

export async function vacateTeamMember(
  apiBase: string,
  headers: Record<string, string>,
  leagueId: string,
  userId: string,
): Promise<void> {
  const r = await fetch(
    `${apiBase}/leagues/${leagueId}/members/${encodeURIComponent(userId)}/vacate`,
    { method: 'POST', headers: { ...headers, 'Content-Type': 'application/json' } },
  )
  if (!r.ok) throw new Error(await r.text())
}

export async function removeLeagueMember(
  apiBase: string,
  headers: Record<string, string>,
  leagueId: string,
  userId: string,
): Promise<void> {
  const r = await fetch(`${apiBase}/leagues/${leagueId}/members/${encodeURIComponent(userId)}`, {
    method: 'DELETE',
    headers: { ...headers, 'Content-Type': 'application/json' },
  })
  if (!r.ok) throw new Error(await r.text())
}

export async function revokeLeagueInvite(
  apiBase: string,
  headers: Record<string, string>,
  leagueId: string,
  inviteId: string,
): Promise<void> {
  const r = await fetch(`${apiBase}/leagues/${leagueId}/invites/${encodeURIComponent(inviteId)}`, {
    method: 'DELETE',
    headers: { ...headers, 'Content-Type': 'application/json' },
  })
  if (!r.ok) throw new Error(await r.text())
}
