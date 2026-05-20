import { useCallback, useMemo, useState } from 'react'

export type CoachEmail = {
  id: string
  sender_type?: string
  sender_name?: string
  subject?: string
  body?: string
  category?: string
  year?: number
  week?: number
  virtual_day?: string
  read?: boolean
  resolved?: boolean
  chosen_choice_id?: string | null
  choices?: { id: string; text: string; effects?: Record<string, number> }[] | null
}

type CoachInboxState = {
  emails?: CoachEmail[]
  program_morale?: number
  public_perception?: number
  admin_trust?: number
  job_security?: number
}

type Props = {
  saveState: any
  saveId: string
  apiBase: string
  headers: Record<string, string>
  onSaveState?: (s: any) => void
  onError: (msg: string) => void
  /** Local zip / offline bundle: inbox actions cannot hit the API */
  readOnly?: boolean
}

const CATEGORIES = [
  { id: 'all', label: 'All' },
  { id: 'performance', label: 'Performance' },
  { id: 'player_issue', label: 'Player / staff' },
  { id: 'admin', label: 'Admin / school' },
  { id: 'boosters', label: 'Boosters / $' },
  { id: 'recruiting', label: 'Recruiting' },
  { id: 'media', label: 'Media' },
  { id: 'community', label: 'Community' },
]

function groupKey(e: CoachEmail): string {
  const y = Number(e.year ?? 0)
  const w = Number(e.week ?? 0)
  return `${y}-W${w}`
}

function sortEmails(a: CoachEmail, b: CoachEmail): number {
  const ya = Number(a.year ?? 0)
  const yb = Number(b.year ?? 0)
  if (yb !== ya) return yb - ya
  const wa = Number(a.week ?? 0)
  const wb = Number(b.week ?? 0)
  if (wb !== wa) return wb - wa
  const da = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'].indexOf(
    String(a.virtual_day || ''),
  )
  const db = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'].indexOf(
    String(b.virtual_day || ''),
  )
  if (da !== db) return db - da
  return String(b.id).localeCompare(String(a.id))
}

export default function CoachInboxPanel({
  saveState,
  saveId,
  apiBase,
  headers,
  onSaveState,
  onError,
  readOnly = false,
}: Props) {
  const leagueStateName =
    typeof saveState?.state === 'string' && saveState.state.trim() ? saveState.state.trim() : null
  const inbox = (saveState?.coach_inbox || {}) as CoachInboxState
  const emails = useMemo(() => (Array.isArray(inbox.emails) ? inbox.emails : []) as CoachEmail[], [inbox.emails])
  const [filterCat, setFilterCat] = useState('all')
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const filtered = useMemo(() => {
    const rows = [...emails]
    rows.sort(sortEmails)
    if (filterCat === 'all') return rows
    return rows.filter((e) => String(e.category || '') === filterCat)
  }, [emails, filterCat])

  const grouped = useMemo(() => {
    const m = new Map<string, CoachEmail[]>()
    for (const e of filtered) {
      const k = groupKey(e)
      if (!m.has(k)) m.set(k, [])
      m.get(k)!.push(e)
    }
    return Array.from(m.entries()).sort((a, b) => b[0].localeCompare(a[0]))
  }, [filtered])

  const selected = useMemo(
    () => (selectedId ? emails.find((e) => e.id === selectedId) || null : null),
    [emails, selectedId],
  )

  const patchInbox = useCallback(
    async (body: {
      mark_read?: string[]
      choose?: { email_id: string; choice_id: string }
      delete?: string[]
    }) => {
      const r = await fetch(`${apiBase}/saves/${saveId}/coach-inbox`, {
        method: 'PATCH',
        headers: { ...headers, 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!r.ok) {
        const err = await r.json().catch(() => ({}))
        onError(typeof err?.detail === 'string' ? err.detail : 'Inbox update failed')
        return false
      }
      const data = await r.json()
      if (data?.state) onSaveState?.(data.state)
      return true
    },
    [apiBase, headers, onError, onSaveState, saveId],
  )

  const deleteEmail = useCallback(
    async (email: CoachEmail) => {
      if (!email?.id) return

      if (readOnly) {
        if (!onSaveState) return
        const prev = (saveState?.coach_inbox || {}) as CoachInboxState
        const list = Array.isArray(prev.emails) ? prev.emails : []
        onSaveState({
          ...saveState,
          coach_inbox: {
            ...prev,
            emails: list.filter((row) => row.id !== email.id),
          },
        })
        setSelectedId(null)
        return
      }

      const ok = await patchInbox({ delete: [email.id] })
      if (ok) setSelectedId(null)
    },
    [onSaveState, patchInbox, readOnly, saveState],
  )

  const openEmail = async (e: CoachEmail) => {
    setSelectedId(e.id)
    if (!e.read && !readOnly) {
      await patchInbox({ mark_read: [e.id] })
    }
  }

  const meter = (label: string, v: number | undefined) => (
    <div className="coach-inbox-meter">
      <span className="coach-inbox-meter-label">{label}</span>
      <div className="coach-inbox-meter-bar">
        <div className="coach-inbox-meter-fill" style={{ width: `${Math.max(0, Math.min(100, Number(v ?? 50)))}%` }} />
      </div>
      <span className="coach-inbox-meter-num">{Math.round(Number(v ?? 50))}</span>
    </div>
  )

  const unread = emails.filter((e) => !e.read).length

  return (
    <div className="coach-inbox-root">
      <div className="coach-inbox-header">
        <div>
          <div className="coach-inbox-title">Coach inbox</div>
          <div className="coach-inbox-sub">
            {leagueStateName ? (
              <>
                <strong>{leagueStateName}</strong> high school football — weekly messages scaled by program prestige.
              </>
            ) : (
              <>Weekly messages scaled by program prestige.</>
            )}{' '}
            Read mail and respond when choices appear — it shifts morale, trust, and how loud the outside noise gets.
          </div>
        </div>
        <div className="coach-inbox-meters">
          {meter('Team morale', inbox.program_morale)}
          {meter('Public perception', inbox.public_perception)}
          {meter('Admin trust', inbox.admin_trust)}
          {meter('Job security', inbox.job_security)}
        </div>
      </div>

      {readOnly ? (
        <div className="coach-inbox-readonly-banner" role="status">
          Imported save (local): you can read and delete mail here; mark read and responses need a cloud save.
        </div>
      ) : null}

      <div className="coach-inbox-toolbar">
        <span className="coach-inbox-unread">{unread} unread</span>
        <label className="coach-inbox-filter">
          Filter
          <select
            className="teamhome-select"
            value={filterCat}
            onChange={(ev) => setFilterCat(ev.target.value)}
            aria-label="Filter by category"
          >
            {CATEGORIES.map((c) => (
              <option key={c.id} value={c.id}>
                {c.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="coach-inbox-panes">
        <div className="coach-inbox-list" role="navigation" aria-label="Email list">
          {grouped.length === 0 ? (
            <div className="coach-inbox-empty">
              No messages yet. Reload the save (starter pack needs a user team), then use Continue after each week for
              more mail.
            </div>
          ) : (
            grouped.map(([gk, rows]) => (
              <div key={gk} className="coach-inbox-group">
                <div className="coach-inbox-group-label">{gk.replace('-', ' · ')}</div>
                {rows.map((e) => (
                  <button
                    key={e.id}
                    type="button"
                    className={`coach-inbox-row${selectedId === e.id ? ' coach-inbox-row--active' : ''}${e.read ? '' : ' coach-inbox-row--unread'}`}
                    onClick={() => openEmail(e)}
                  >
                    <div className="coach-inbox-row-top">
                      <span className="coach-inbox-sender">{e.sender_name || 'Unknown'}</span>
                      <span className="coach-inbox-day">{e.virtual_day || '—'}</span>
                    </div>
                    <div className="coach-inbox-subject">{e.subject || '(no subject)'}</div>
                    <div className="coach-inbox-meta">
                      <span className="coach-inbox-tag">{e.sender_type || ''}</span>
                      {e.category ? <span className="coach-inbox-tag coach-inbox-tag--muted">{e.category}</span> : null}
                    </div>
                  </button>
                ))}
              </div>
            ))
          )}
        </div>

        <div className="coach-inbox-detail" role="region" aria-label="Message detail">
          {!selected ? (
            <div className="coach-inbox-empty coach-inbox-empty--detail">Select a message</div>
          ) : (
            <>
              <div className="coach-inbox-detail-head">
                <div className="coach-inbox-detail-head-row">
                  <div className="coach-inbox-detail-subject">{selected.subject}</div>
                  <button
                    type="button"
                    className="coach-inbox-delete"
                    onClick={() => void deleteEmail(selected)}
                    title={readOnly ? 'Remove from this imported save (not synced to cloud)' : 'Delete this message'}
                  >
                    Delete
                  </button>
                </div>
                <div className="coach-inbox-detail-from">
                  <strong>{selected.sender_name}</strong>
                  <span className="coach-inbox-detail-type">{selected.sender_type}</span>
                  <span className="coach-inbox-detail-when">
                    Year {selected.year} · Week {selected.week} · {selected.virtual_day}
                  </span>
                </div>
              </div>
              <div className="coach-inbox-body">{selected.body}</div>
              {selected.choices && selected.choices.length > 0 && !selected.resolved ? (
                <div className="coach-inbox-choices">
                  <div className="coach-inbox-choices-title">Respond</div>
                  <div className="coach-inbox-choice-btns">
                    {selected.choices.map((c) => (
                      <button
                        key={c.id}
                        type="button"
                        className="coach-inbox-choice"
                        disabled={readOnly}
                        title={readOnly ? 'Not available for local import saves' : undefined}
                        onClick={async () => {
                          if (readOnly) return
                          await patchInbox({ choose: { email_id: selected.id, choice_id: c.id } })
                        }}
                      >
                        {c.text}
                      </button>
                    ))}
                  </div>
                </div>
              ) : null}
              {selected.resolved ? (
                <div className="coach-inbox-resolved">You responded to this thread.</div>
              ) : null}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
