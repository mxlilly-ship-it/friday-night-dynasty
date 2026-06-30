import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { isBrowserSaveId } from './browserSave'
import { sortInboxEmailsForDisplay, inboxEmailDisplayTitle } from './inSeasonDashboardData'

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
  getLiveSaveState?: () => any
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

function nextEmailIdAfterDelete(emailId: string, list: CoachEmail[]): string | null {
  const idx = list.findIndex((e) => e.id === emailId)
  if (idx < 0) return list[0]?.id ?? null
  if (idx < list.length - 1) return list[idx + 1].id
  if (idx > 0) return list[idx - 1].id
  return null
}

function inboxEmailCount(state: any): number {
  return Array.isArray(state?.coach_inbox?.emails) ? state.coach_inbox.emails.length : 0
}

/** Prefer the snapshot that still has the full mail list when refs lag behind React state. */
function mergeInboxStateForPatch(primary: any, secondary: any): any {
  const merged = structuredClone(primary ?? {})
  const primaryEmails = merged?.coach_inbox?.emails
  const secondaryEmails = secondary?.coach_inbox?.emails
  const primaryN = Array.isArray(primaryEmails) ? primaryEmails.length : 0
  const secondaryN = Array.isArray(secondaryEmails) ? secondaryEmails.length : 0
  if (secondaryN > primaryN) {
    merged.coach_inbox = {
      ...(merged.coach_inbox ?? {}),
      ...(secondary.coach_inbox ?? {}),
      emails: structuredClone(secondaryEmails),
    }
  }
  return merged
}

function markEmailsReadLocally(state: any, ids: string[]): any {
  if (!ids.length) return state
  const next = structuredClone(state ?? {})
  const inbox = { ...(next.coach_inbox ?? {}) }
  const emails = Array.isArray(inbox.emails) ? inbox.emails.map((row: CoachEmail) => ({ ...row })) : []
  const want = new Set(ids)
  for (const row of emails) {
    if (want.has(String(row.id))) row.read = true
  }
  next.coach_inbox = { ...inbox, emails }
  return next
}

/** Avoid wiping mail when a patch response returns an older inbox snapshot. */
function mergeInboxPatchResponse(prev: any, next: any, deletedIds: string[] = []): any {
  if (!next) return prev
  if (!prev) return next
  const prevN = inboxEmailCount(prev)
  const nextN = inboxEmailCount(next)
  const allowedDrop = deletedIds.length
  if (nextN >= prevN - allowedDrop) return next

  const out = structuredClone(next)
  const nextById = new Map<string, CoachEmail>(
    (next.coach_inbox?.emails ?? []).map((e: CoachEmail) => [String(e.id), e]),
  )
  const mergedEmails = (prev.coach_inbox?.emails ?? []).map((e: CoachEmail) => {
    const updated = nextById.get(String(e.id))
    return updated ? { ...e, ...updated } : e
  })
  for (const [id, row] of nextById) {
    if (!mergedEmails.some((e: CoachEmail) => String(e.id) === id)) mergedEmails.push(row)
  }
  out.coach_inbox = { ...(out.coach_inbox ?? {}), emails: mergedEmails }
  return out
}

/** Scroll within the inbox list only — avoids jumping the whole Team page. */
function scrollInboxRowIntoView(listEl: HTMLElement | null, emailId: string) {
  if (!listEl || !emailId) return
  const row = listEl.querySelector(`[data-coach-inbox-id="${CSS.escape(emailId)}"]`) as HTMLElement | null
  if (!row) return
  const listRect = listEl.getBoundingClientRect()
  const rowRect = row.getBoundingClientRect()
  if (rowRect.top < listRect.top) {
    listEl.scrollTop -= listRect.top - rowRect.top
  } else if (rowRect.bottom > listRect.bottom) {
    listEl.scrollTop += rowRect.bottom - listRect.bottom
  }
}

export default function CoachInboxPanel({
  saveState,
  saveId,
  apiBase,
  headers,
  getLiveSaveState,
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
  const listRef = useRef<HTMLDivElement | null>(null)
  const detailRef = useRef<HTMLDivElement | null>(null)

  const filtered = useMemo(() => {
    const rows =
      filterCat === 'all' ? emails : emails.filter((e) => String(e.category || '') === filterCat)
    return sortInboxEmailsForDisplay(rows) as CoachEmail[]
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

  useEffect(() => {
    if (!selectedId) return
    if (filtered.some((e) => e.id === selectedId)) return
    setSelectedId(filtered[0]?.id ?? null)
  }, [filtered, selectedId])

  const showEmailDetail = useCallback((e: CoachEmail, opts?: { scrollList?: boolean }) => {
    setSelectedId(e.id)
    requestAnimationFrame(() => {
      detailRef.current?.scrollTo({ top: 0 })
      if (opts?.scrollList) scrollInboxRowIntoView(listRef.current, e.id)
    })
  }, [])

  const patchInbox = useCallback(
    async (body: {
      mark_read?: string[]
      choose?: { email_id: string; choice_id: string }
      delete?: string[]
    }) => {
      const isLocalBundle = isBrowserSaveId(saveId)
      const live = getLiveSaveState?.() ?? saveState
      const mergedLive = isLocalBundle ? mergeInboxStateForPatch(live, saveState) : live
      const url = isLocalBundle
        ? `${apiBase}/sim/coach-inbox`
        : `${apiBase}/saves/${saveId}/coach-inbox`
      const reqBody = isLocalBundle ? { state: mergedLive, ...body } : body
      const r = await fetch(url, {
        method: 'PATCH',
        headers: { ...headers, 'Content-Type': 'application/json' },
        body: JSON.stringify(reqBody),
      })
      if (!r.ok) {
        const err = await r.json().catch(() => ({}))
        onError(typeof err?.detail === 'string' ? err.detail : 'Inbox update failed')
        return false
      }
      const data = await r.json()
      if (data?.state) {
        const prev = getLiveSaveState?.() ?? saveState
        const safe = mergeInboxPatchResponse(prev, data.state, body.delete ?? [])
        onSaveState?.(safe)
      }
      return true
    },
    [apiBase, headers, getLiveSaveState, onError, onSaveState, saveId, saveState],
  )

  const openEmail = useCallback(
    async (e: CoachEmail, opts?: { scrollList?: boolean }) => {
      showEmailDetail(e, opts)
      if (!e.read) {
        const before = getLiveSaveState?.() ?? saveState
        onSaveState?.(markEmailsReadLocally(before, [e.id]))
        await patchInbox({ mark_read: [e.id] })
      }
    },
    [getLiveSaveState, onSaveState, patchInbox, saveState, showEmailDetail],
  )

  const moveSelection = useCallback(
    (direction: -1 | 1) => {
      if (filtered.length === 0) return
      const idx = selectedId ? filtered.findIndex((e) => e.id === selectedId) : -1
      let nextIdx: number
      if (idx < 0) {
        nextIdx = direction === 1 ? 0 : filtered.length - 1
      } else {
        nextIdx = idx + direction
        if (nextIdx < 0 || nextIdx >= filtered.length) return
      }
      const next = filtered[nextIdx]
      void openEmail(next, { scrollList: true })
    },
    [filtered, openEmail, selectedId],
  )

  useEffect(() => {
    const onKeyDown = (ev: KeyboardEvent) => {
      if (ev.key !== 'ArrowUp' && ev.key !== 'ArrowDown') return
      const target = ev.target as HTMLElement | null
      if (target?.closest('input, textarea, select, button.coach-inbox-choice')) return
      if (filtered.length === 0) return
      ev.preventDefault()
      moveSelection(ev.key === 'ArrowDown' ? 1 : -1)
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [filtered.length, moveSelection])

  const deleteEmail = useCallback(
    async (email: CoachEmail) => {
      if (!email?.id) return
      const nextId = nextEmailIdAfterDelete(email.id, filtered)

      const ok = await patchInbox({ delete: [email.id] })
      if (ok) setSelectedId(nextId)
    },
    [filtered, patchInbox],
  )

  const deleteAllEmails = useCallback(async () => {
    if (emails.length === 0) return
    if (!window.confirm(`Delete all ${emails.length} message${emails.length === 1 ? '' : 's'}?`)) return

    const ok = await patchInbox({ delete: emails.map((e) => e.id) })
    if (ok) setSelectedId(null)
  }, [emails, patchInbox])

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
        <div className="coach-inbox-toolbar-actions">
          <button
            type="button"
            className="coach-inbox-delete"
            disabled={emails.length === 0}
            onClick={() => void deleteAllEmails()}
            title={readOnly ? 'Remove all mail from this imported save (not synced to cloud)' : 'Delete all messages'}
          >
            Delete all
          </button>
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
      </div>

      <div className="coach-inbox-panes">
        <div className="coach-inbox-list" ref={listRef} role="navigation" aria-label="Email list">
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
                    data-coach-inbox-id={e.id}
                    className={`coach-inbox-row${selectedId === e.id ? ' coach-inbox-row--active' : ''}${e.read ? '' : ' coach-inbox-row--unread'}`}
                    onClick={() => void openEmail(e)}
                  >
                    <div className="coach-inbox-row-top">
                      <span className="coach-inbox-sender">{e.sender_name || 'Unknown'}</span>
                      <span className="coach-inbox-day">{e.virtual_day || '—'}</span>
                    </div>
                    <div className="coach-inbox-subject">{inboxEmailDisplayTitle(e)}</div>
                    <div className="coach-inbox-meta">
                      <span className="coach-inbox-tag">{e.sender_type || ''}</span>
                      {e.category ? <span className="coach-inbox-tag coach-inbox-tag--muted">{e.category}</span> : null}
                      {e.read ? <span className="coach-inbox-tag coach-inbox-tag--read">Read</span> : null}
                    </div>
                  </button>
                ))}
              </div>
            ))
          )}
        </div>

        <div className="coach-inbox-detail" ref={detailRef} role="region" aria-label="Message detail">
          {!selected ? (
            <div className="coach-inbox-empty coach-inbox-empty--detail">
              Select a message{filtered.length > 0 ? ' (↑ ↓ to browse)' : ''}
            </div>
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
