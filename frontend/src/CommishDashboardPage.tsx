import { useEffect, useState } from 'react'
import './CommishDashboardPage.css'
import type { CommishDashboardData } from './multiplayer'

const DOW_OPTIONS = [
  { value: 0, label: 'Monday' },
  { value: 1, label: 'Tuesday' },
  { value: 2, label: 'Wednesday' },
  { value: 3, label: 'Thursday' },
  { value: 4, label: 'Friday' },
  { value: 5, label: 'Saturday' },
  { value: 6, label: 'Sunday' },
]

type CommishDashboardPageProps = {
  data: CommishDashboardData
  onBack: () => void
  onRefresh: () => Promise<void>
  onSimWeek: () => Promise<string>
  simWeekBusy?: boolean
  onInvite: (email: string) => Promise<{ email_sent?: boolean } | void>
  onAssign: (email: string, teamName: string) => Promise<string>
  onResetPin: (userId: string) => Promise<string>
  onSaveSettings: (patch: {
    advance_mode: string
    advance_deadline_dow: number | null
    advance_deadline_time_local: string
    submit_lockout_minutes: number
    timezone: string
  }) => Promise<void>
  onOpenLeagueHub?: () => void
  onOpenMyDynasty?: () => void
  myDynastyBusy?: boolean
  onSubmitWeek?: () => void
  onUnsubmitWeek?: () => void
  submitBusy?: boolean
  hasCoachTeam?: boolean
  onVacate?: (userId: string) => Promise<void>
  onRemove?: (userId: string) => Promise<void>
  onRevokeInvite?: (inviteId: string) => Promise<void>
}

export default function CommishDashboardPage({
  data,
  onBack,
  onRefresh,
  onSimWeek,
  simWeekBusy = false,
  onInvite,
  onAssign,
  onResetPin,
  onSaveSettings,
  onOpenLeagueHub,
  onOpenMyDynasty,
  myDynastyBusy = false,
  onSubmitWeek,
  onUnsubmitWeek,
  submitBusy = false,
  hasCoachTeam = false,
  onVacate,
  onRemove,
  onRevokeInvite,
}: CommishDashboardPageProps) {
  const readOnly = data.can_manage === false || data.is_read_only_admin === true
  const coachTeam = data.acting_team_name || null
  const showCoachActions = Boolean(hasCoachTeam || coachTeam)
  const submitted = Boolean(data.your_status?.submitted)
  const [inviteEmail, setInviteEmail] = useState('')
  const [assignEmail, setAssignEmail] = useState('')
  const [assignTeam, setAssignTeam] = useState(data.vacant_teams[0] ?? '')
  const [busy, setBusy] = useState('')
  const [flash, setFlash] = useState('')
  const [pinFlash, setPinFlash] = useState('')

  const [advanceMode, setAdvanceMode] = useState(data.settings.advance_mode)
  const [deadlineDow, setDeadlineDow] = useState<number | ''>(
    data.settings.advance_deadline_dow ?? '',
  )
  const [deadlineTime, setDeadlineTime] = useState(data.settings.advance_deadline_time_local)
  const [lockoutMinutes, setLockoutMinutes] = useState(String(data.settings.submit_lockout_minutes))
  const [timezone, setTimezone] = useState(data.settings.timezone)
  const [settingsBusy, setSettingsBusy] = useState(false)

  useEffect(() => {
    setAdvanceMode(data.settings.advance_mode)
    setDeadlineDow(data.settings.advance_deadline_dow ?? '')
    setDeadlineTime(data.settings.advance_deadline_time_local)
    setLockoutMinutes(String(data.settings.submit_lockout_minutes))
    setTimezone(data.settings.timezone)
    if (!assignTeam && data.vacant_teams.length) {
      setAssignTeam(data.vacant_teams[0])
    }
  }, [data, assignTeam])

  async function runAction(key: string, fn: () => Promise<void>) {
    setBusy(key)
    setFlash('')
    setPinFlash('')
    setErrorLocal('')
    try {
      await fn()
      await onRefresh()
    } catch (e: unknown) {
      setErrorLocal(e instanceof Error ? e.message : 'Action failed')
    } finally {
      setBusy('')
    }
  }

  const [errorLocal, setErrorLocal] = useState('')

  return (
    <div className="cdash-root ldash-root">
      <header className="cdash-header">
        <div className="cdash-title-block">
          <h1>{data.league_name}</h1>
          <div className="cdash-subtitle">
            {readOnly ? 'Admin view (read-only)' : 'Commissioner dashboard'}
          </div>
        </div>
        <div className="cdash-header-actions">
          <button type="button" className="ldash-back-btn" onClick={onBack}>
            ← Leagues
          </button>
          {showCoachActions && onOpenLeagueHub ? (
            <button type="button" className="cdash-btn cdash-btn--blue" onClick={onOpenLeagueHub}>
              League hub
            </button>
          ) : null}
          {showCoachActions && onOpenMyDynasty ? (
            <button
              type="button"
              className="cdash-btn cdash-btn--gold"
              disabled={myDynastyBusy}
              onClick={onOpenMyDynasty}
            >
              {myDynastyBusy ? 'Opening…' : 'My dynasty'}
            </button>
          ) : null}
          {showCoachActions && onSubmitWeek && !submitted ? (
            <button
              type="button"
              className="cdash-btn cdash-btn--gold"
              disabled={submitBusy || Boolean(busy)}
              onClick={() =>
                void runAction('submit', async () => {
                  await onSubmitWeek()
                  setFlash('Week submitted.')
                })
              }
            >
              {submitBusy || busy === 'submit' ? 'Submitting…' : 'Submit week'}
            </button>
          ) : null}
          {showCoachActions && onUnsubmitWeek && submitted ? (
            <button
              type="button"
              className="cdash-btn"
              disabled={submitBusy || Boolean(busy) || data.your_status?.can_unsubmit === false}
              title={
                data.your_status?.can_unsubmit === false
                  ? 'Locked — too close to the advance deadline'
                  : undefined
              }
              onClick={() =>
                void runAction('unsubmit', async () => {
                  await onUnsubmitWeek()
                  setFlash('Week unsubmitted — you can keep prepping.')
                })
              }
            >
              {submitBusy || busy === 'unsubmit' ? '…' : 'Unsubmit'}
            </button>
          ) : null}
          {!readOnly ? (
            <>
          <button
            type="button"
            className="cdash-btn cdash-btn--gold"
            disabled={simWeekBusy || Boolean(busy)}
            onClick={() => {
              void runAction('sim', async () => {
                const msg = await onSimWeek()
                setFlash(msg)
              })
            }}
          >
            {simWeekBusy || busy === 'sim' ? 'Simulating…' : 'Sim week'}
          </button>
            </>
          ) : null}
        </div>
      </header>

      <div className="cdash-status-row">
        <div>
          <div className="cdash-status-pill cdash-status-pill--gold">{data.week_label}</div>
        </div>
        <div>
          <div className="cdash-status-pill">
            Submitted {data.progress.submitted}/{data.progress.total} ({data.progress.percent}%)
          </div>
          <div className="cdash-progress-bar">
            <div className="cdash-progress-fill" style={{ width: `${data.progress.percent}%` }} />
          </div>
        </div>
        {coachTeam ? (
          <div className="cdash-status-pill">
            Your team: {coachTeam}
            {submitted ? ' · Submitted' : ' · Not submitted'}
          </div>
        ) : null}
        {data.settings.countdown_value ? (
          <div className="cdash-status-pill">Advance in {data.settings.countdown_value}</div>
        ) : null}
        <div className="cdash-status-pill">
          Mode: {data.settings.advance_mode === 'auto' ? 'Auto-advance' : 'Manual'}
        </div>
      </div>

      {flash ? <div className="cdash-flash" style={{ margin: '12px 32px 0' }}>{flash}</div> : null}
      {pinFlash ? (
        <div className="cdash-flash cdash-flash--pin" style={{ margin: '12px 32px 0' }}>
          New PIN: {pinFlash}
        </div>
      ) : null}
      {errorLocal ? (
        <div className="fnd-error" style={{ margin: '12px 32px 0' }}>
          {errorLocal}
        </div>
      ) : null}

      <div className="cdash-grid">
        {!readOnly ? (
        <>
        <section className="cdash-panel">
          <div className="cdash-panel-head">Invite coach</div>
          <div className="cdash-panel-body">
            <p className="cdash-subtitle" style={{ marginTop: 0, marginBottom: 12 }}>
              Send an invite by email. They must sign in to FND once before you can assign a team.
            </p>
            <div className="cdash-form-row">
              <input
                type="email"
                className="cdash-input"
                placeholder="coach@email.com"
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
              />
              <button
                type="button"
                className="cdash-btn cdash-btn--gold"
                disabled={!inviteEmail.trim() || Boolean(busy)}
                onClick={() =>
                  void runAction('invite', async () => {
                    const res = await onInvite(inviteEmail.trim())
                    setInviteEmail('')
                    setFlash(
                      res && res.email_sent
                        ? 'Invite sent — email delivered.'
                        : 'Invite saved. Email delivery is not configured on this server (they’ll see it when they sign in).',
                    )
                  })
                }
              >
                {busy === 'invite' ? 'Sending…' : 'Invite'}
              </button>
            </div>
            {data.pending_invites.length ? (
              <ul className="cdash-invite-list" style={{ marginTop: 16 }}>
                {data.pending_invites.map((inv) => (
                  <li key={inv.invite_id}>
                    <span>{inv.email}</span>
                    <span style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                      <span className="cdash-tag cdash-tag--wait">Pending</span>
                      {!readOnly && onRevokeInvite ? (
                        <button
                          type="button"
                          className="cdash-btn cdash-btn--small"
                          disabled={Boolean(busy)}
                          onClick={() =>
                            void runAction(`revoke-${inv.invite_id}`, async () => {
                              await onRevokeInvite(inv.invite_id)
                              setFlash(`Revoked invite for ${inv.email}.`)
                            })
                          }
                        >
                          Revoke
                        </button>
                      ) : null}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="cdash-empty">No pending invites.</p>
            )}
          </div>
        </section>

        <section className="cdash-panel">
          <div className="cdash-panel-head">Assign team</div>
          <div className="cdash-panel-body">
            <div className="cdash-form-row">
              <input
                type="email"
                className="cdash-input"
                placeholder="coach@email.com"
                value={assignEmail}
                onChange={(e) => setAssignEmail(e.target.value)}
              />
            </div>
            <div className="cdash-form-row">
              <select
                className="cdash-select"
                value={assignTeam}
                onChange={(e) => setAssignTeam(e.target.value)}
              >
                {data.vacant_teams.length === 0 ? (
                  <option value="">No vacant teams</option>
                ) : (
                  data.vacant_teams.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))
                )}
              </select>
              <button
                type="button"
                className="cdash-btn cdash-btn--gold"
                disabled={!assignEmail.trim() || !assignTeam || Boolean(busy)}
                onClick={() =>
                  void runAction('assign', async () => {
                    const pin = await onAssign(assignEmail.trim(), assignTeam)
                    setAssignEmail('')
                    setPinFlash(pin)
                    setFlash(`Assigned ${assignTeam}. Share the PIN with the coach.`)
                  })
                }
              >
                {busy === 'assign' ? 'Assigning…' : 'Assign & generate PIN'}
              </button>
            </div>
          </div>
        </section>
        </>
        ) : data.pending_invites.length ? (
        <section className="cdash-panel cdash-panel--wide">
          <div className="cdash-panel-head">Pending invites</div>
          <div className="cdash-panel-body">
            <ul className="cdash-invite-list">
              {data.pending_invites.map((inv) => (
                <li key={inv.invite_id}>
                  <span>{inv.email}</span>
                  <span className="cdash-tag cdash-tag--wait">Pending</span>
                </li>
              ))}
            </ul>
          </div>
        </section>
        ) : null}

        <section className="cdash-panel cdash-panel--wide">
          <div className="cdash-panel-head">Members</div>
          <div className="cdash-panel-body" style={{ overflowX: 'auto' }}>
            {data.members.length === 0 ? (
              <p className="cdash-empty">No members yet.</p>
            ) : (
              <table className="cdash-table">
                <thead>
                  <tr>
                    <th>Coach</th>
                    <th>Team</th>
                    <th>Status</th>
                    <th>Week</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {data.members.map((m) => (
                    <tr key={m.user_id}>
                      <td>{m.email || m.user_id}</td>
                      <td>{m.team_name ?? '—'}</td>
                      <td>
                        {!m.team_name ? (
                          <span className="cdash-tag cdash-tag--wait">Unassigned</span>
                        ) : m.coach_setup_complete ? (
                          <span className="cdash-tag cdash-tag--ok">Active</span>
                        ) : (
                          <span className="cdash-tag cdash-tag--wait">Setup pending</span>
                        )}
                      </td>
                      <td>
                        {m.team_name ? (
                          m.submitted ? (
                            <span className="cdash-tag cdash-tag--ok">Submitted</span>
                          ) : (
                            <span className="cdash-tag cdash-tag--wait">Not submitted</span>
                          )
                        ) : (
                          '—'
                        )}
                      </td>
                      <td>
                        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                        {m.team_name && !readOnly ? (
                          <button
                            type="button"
                            className="cdash-btn cdash-btn--small"
                            disabled={Boolean(busy)}
                            onClick={() =>
                              void runAction(`pin-${m.user_id}`, async () => {
                                const pin = await onResetPin(m.user_id)
                                setPinFlash(pin)
                                setFlash(`PIN reset for ${m.email || m.team_name}.`)
                              })
                            }
                          >
                            {busy === `pin-${m.user_id}` ? '…' : 'Reset PIN'}
                          </button>
                        ) : null}
                        {m.team_name && !readOnly && onVacate ? (
                          <button
                            type="button"
                            className="cdash-btn cdash-btn--small"
                            disabled={Boolean(busy)}
                            onClick={() =>
                              void runAction(`vacate-${m.user_id}`, async () => {
                                await onVacate(m.user_id)
                                setFlash(`Vacated ${m.team_name}.`)
                              })
                            }
                          >
                            Vacate
                          </button>
                        ) : null}
                        {!readOnly && onRemove ? (
                          <button
                            type="button"
                            className="cdash-btn cdash-btn--small"
                            disabled={Boolean(busy)}
                            onClick={() =>
                              void runAction(`remove-${m.user_id}`, async () => {
                                await onRemove(m.user_id)
                                setFlash(`Removed ${m.email || m.user_id}.`)
                              })
                            }
                          >
                            Remove
                          </button>
                        ) : null}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </section>

        <section className="cdash-panel">
          <div className="cdash-panel-head">Vacant teams ({data.vacant_teams.length})</div>
          <div className="cdash-panel-body">
            {data.vacant_teams.length === 0 ? (
              <p className="cdash-empty">All teams are assigned.</p>
            ) : (
              <div className="cdash-vacant-list">
                {data.vacant_teams.map((t) => (
                  <span key={t} className="cdash-vacant-chip">
                    {t}
                  </span>
                ))}
              </div>
            )}
          </div>
        </section>

        <section className="cdash-panel">
          <div className="cdash-panel-head">Advance settings</div>
          <div className="cdash-panel-body">
            {readOnly ? (
              <p className="cdash-subtitle" style={{ margin: 0 }}>
                Mode: {data.settings.advance_mode === 'auto' ? 'Auto-advance' : 'Manual'} · Lockout{' '}
                {data.settings.submit_lockout_minutes}m · {data.settings.timezone}
              </p>
            ) : (
            <>
            <div className="cdash-settings-grid">
              <div className="cdash-field">
                <label htmlFor="cdash-mode">Advance mode</label>
                <select
                  id="cdash-mode"
                  className="cdash-select"
                  value={advanceMode}
                  onChange={(e) => setAdvanceMode(e.target.value)}
                >
                  <option value="manual">Manual (commish sims)</option>
                  <option value="auto">Auto at deadline</option>
                </select>
              </div>
              <div className="cdash-field">
                <label htmlFor="cdash-tz">Timezone</label>
                <input
                  id="cdash-tz"
                  className="cdash-input"
                  value={timezone}
                  onChange={(e) => setTimezone(e.target.value)}
                />
              </div>
              <div className="cdash-field">
                <label htmlFor="cdash-dow">Deadline day</label>
                <select
                  id="cdash-dow"
                  className="cdash-select"
                  value={deadlineDow === '' ? '' : String(deadlineDow)}
                  onChange={(e) =>
                    setDeadlineDow(e.target.value === '' ? '' : Number(e.target.value))
                  }
                >
                  <option value="">Not set</option>
                  {DOW_OPTIONS.map((d) => (
                    <option key={d.value} value={d.value}>
                      {d.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="cdash-field">
                <label htmlFor="cdash-time">Deadline time</label>
                <input
                  id="cdash-time"
                  type="time"
                  className="cdash-input"
                  value={deadlineTime}
                  onChange={(e) => setDeadlineTime(e.target.value)}
                />
              </div>
              <div className="cdash-field">
                <label htmlFor="cdash-lockout">Submit lockout (minutes)</label>
                <input
                  id="cdash-lockout"
                  type="number"
                  min={0}
                  max={120}
                  className="cdash-input"
                  value={lockoutMinutes}
                  onChange={(e) => setLockoutMinutes(e.target.value)}
                />
              </div>
            </div>
            <div style={{ marginTop: 14 }}>
              <button
                type="button"
                className="cdash-btn cdash-btn--gold"
                disabled={settingsBusy}
                onClick={() => {
                  setSettingsBusy(true)
                  setErrorLocal('')
                  void onSaveSettings({
                    advance_mode: advanceMode,
                    advance_deadline_dow: deadlineDow === '' ? null : deadlineDow,
                    advance_deadline_time_local: deadlineTime,
                    submit_lockout_minutes: Number(lockoutMinutes) || 0,
                    timezone: timezone.trim() || 'America/New_York',
                  })
                    .then(() => {
                      setFlash('Settings saved.')
                      return onRefresh()
                    })
                    .catch((e: unknown) =>
                      setErrorLocal(e instanceof Error ? e.message : 'Could not save settings'),
                    )
                    .finally(() => setSettingsBusy(false))
                }}
              >
                {settingsBusy ? 'Saving…' : 'Save settings'}
              </button>
            </div>
            </>
            )}
          </div>
        </section>
      </div>
    </div>
  )
}
