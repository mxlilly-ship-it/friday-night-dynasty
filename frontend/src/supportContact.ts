export type SupportCategory = 'question' | 'bug' | 'refund' | 'account' | 'other'

export const SUPPORT_CATEGORIES: { id: SupportCategory; label: string }[] = [
  { id: 'question', label: 'General question' },
  { id: 'bug', label: 'Bug report' },
  { id: 'refund', label: 'Refund request' },
  { id: 'account', label: 'Account / login help' },
  { id: 'other', label: 'Other' },
]

export type SupportContactPayload = {
  category: SupportCategory
  message: string
  contact_email?: string
  page_url?: string
}

export async function submitSupportContact(
  apiBase: string,
  payload: SupportContactPayload,
  headers: Record<string, string> = {},
): Promise<{ ticket_id: string; message: string }> {
  const r = await fetch(`${apiBase}/support/contact`, {
    method: 'POST',
    headers: { ...headers, 'Content-Type': 'application/json' },
    body: JSON.stringify({
      category: payload.category,
      message: payload.message,
      contact_email: payload.contact_email || undefined,
      page_url: payload.page_url || window.location.href,
    }),
  })
  const text = await r.text()
  let data: { ticket_id?: string; message?: string; detail?: unknown } | null = null
  try {
    data = text ? JSON.parse(text) : null
  } catch {
    data = null
  }
  if (!r.ok) {
    const detail = data?.detail
    throw new Error(typeof detail === 'string' ? detail : text || `Support request failed (${r.status})`)
  }
  return {
    ticket_id: String(data?.ticket_id ?? ''),
    message: String(data?.message ?? 'Message sent.'),
  }
}
