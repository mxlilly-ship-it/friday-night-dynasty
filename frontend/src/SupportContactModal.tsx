import { useEffect, useMemo, useState } from 'react'
import './SupportContactModal.css'
import { SUPPORT_CATEGORIES, submitSupportContact, type SupportCategory } from './supportContact'
import { SUPPORT_CONTACT_EMAIL } from './legalContent'

type Props = {
  open: boolean
  onClose: () => void
  apiBase: string
  getAuthHeaders: () => Promise<Record<string, string>>
  defaultEmail?: string
  onSuccess?: (message: string) => void
  onError?: (message: string) => void
}

export default function SupportContactModal({
  open,
  onClose,
  apiBase,
  getAuthHeaders,
  defaultEmail = '',
  onSuccess,
  onError,
}: Props) {
  const [category, setCategory] = useState<SupportCategory>('question')
  const [email, setEmail] = useState(defaultEmail)
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [localError, setLocalError] = useState('')

  useEffect(() => {
    if (!open) return
    setEmail(defaultEmail)
    setLocalError('')
  }, [open, defaultEmail])

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  const refundNote = useMemo(
    () =>
      category === 'refund'
        ? `Refunds are available within 5 days of purchase. Include the email you used to purchase and the approximate date. Email ${SUPPORT_CONTACT_EMAIL} or submit here — approved refunds are processed through Stripe and remove game access.`
        : '',
    [category],
  )

  if (!open) return null

  async function handleSubmit() {
    setLocalError('')
    const em = email.trim()
    if (!em || !em.includes('@')) {
      setLocalError('Enter a valid email so we can reply.')
      return
    }
    if (message.trim().length < 10) {
      setLocalError('Please enter at least 10 characters.')
      return
    }
    setBusy(true)
    try {
      const headers = await getAuthHeaders()
      const result = await submitSupportContact(
        apiBase,
        { category, message: message.trim(), contact_email: em },
        headers,
      )
      setMessage('')
      onSuccess?.(result.message)
      onClose()
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Could not send message'
      setLocalError(msg)
      onError?.(msg)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div
      className="fnd-support-backdrop"
      role="presentation"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div className="fnd-support-modal" role="dialog" aria-modal="true" aria-labelledby="fnd-support-title">
        <div className="fnd-support-header">
          <h2 id="fnd-support-title">Help &amp; support</h2>
          <button type="button" className="fnd-support-close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>
        <div className="fnd-support-body">
          <p className="fnd-support-intro">
            Questions, bug reports, and refund requests go to the Friday Night Dynasty team. We reply by email.
          </p>
          <label className="fnd-support-field">
            <span>Topic</span>
            <select value={category} onChange={(e) => setCategory(e.target.value as SupportCategory)} disabled={busy}>
              {SUPPORT_CATEGORIES.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.label}
                </option>
              ))}
            </select>
          </label>
          <label className="fnd-support-field">
            <span>Your email</span>
            <input
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              disabled={busy}
            />
          </label>
          <label className="fnd-support-field">
            <span>Message</span>
            <textarea
              rows={6}
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="Describe your question, bug, or refund request…"
              disabled={busy}
            />
          </label>
          {refundNote ? <p className="fnd-support-note">{refundNote}</p> : null}
          {localError ? <p className="fnd-support-error">{localError}</p> : null}
        </div>
        <div className="fnd-support-footer">
          <button type="button" className="teamhome-select" onClick={onClose} disabled={busy}>
            Cancel
          </button>
          <button type="button" className="fnd-title-btn fnd-support-submit" onClick={() => void handleSubmit()} disabled={busy}>
            {busy ? 'Sending…' : 'Send message'}
          </button>
        </div>
      </div>
    </div>
  )
}
