export type BillingStatus = {
  billing_required: boolean
  billing_configured: boolean
  entitled: boolean
  purchased_at: number | null
  trial_available: boolean
  trial_completed: boolean
}

export type ApiErrorDetail = {
  message: string
  code?: string
}

export async function parseApiError(r: Response): Promise<ApiErrorDetail> {
  const raw = await r.text()
  const fallback = `Request failed (${r.status})`
  try {
    const j = JSON.parse(raw) as { detail?: unknown }
    const d = j.detail
    if (typeof d === 'string') {
      const trimmed = d.trim()
      if (trimmed && trimmed.toLowerCase() !== 'none') return { message: trimmed }
    }
    if (d && typeof d === 'object' && !Array.isArray(d)) {
      const obj = d as Record<string, unknown>
      const message = typeof obj.message === 'string' ? obj.message : fallback
      const code = typeof obj.code === 'string' ? obj.code : undefined
      if (message) return { message, code }
    }
    if (Array.isArray(d))
      return {
        message: d.map((x: any) => (typeof x?.msg === 'string' ? x.msg : JSON.stringify(x))).join('; '),
      }
  } catch {
    /* use raw */
  }
  const trimmedRaw = raw.trim()
  return { message: trimmedRaw && trimmedRaw.toLowerCase() !== 'none' ? trimmedRaw : fallback }
}

export async function fetchBillingStatus(
  apiBase: string,
  headers: Record<string, string>,
): Promise<BillingStatus> {
  const r = await fetch(`${apiBase}/billing/status`, { headers })
  if (!r.ok) {
    const text = await r.text()
    throw new Error(text || `Billing status failed (${r.status})`)
  }
  return r.json()
}

export async function createCheckoutSession(
  apiBase: string,
  headers: Record<string, string>,
): Promise<{ checkoutUrl: string; sessionId: string }> {
  const r = await fetch(`${apiBase}/billing/create-checkout-session`, {
    method: 'POST',
    headers: { ...headers, 'Content-Type': 'application/json' },
  })
  const text = await r.text()
  let data: { checkout_url?: string; session_id?: string; detail?: unknown } | null = null
  try {
    data = text ? JSON.parse(text) : null
  } catch {
    data = null
  }
  if (!r.ok) {
    const detail = data?.detail
    throw new Error(typeof detail === 'string' ? detail : text || `Checkout failed (${r.status})`)
  }
  const checkoutUrl = String(data?.checkout_url ?? '').trim()
  const sessionId = String(data?.session_id ?? '').trim()
  if (!checkoutUrl || !sessionId) throw new Error('Server did not return checkout details.')
  return { checkoutUrl, sessionId }
}

export async function syncBillingAccess(
  apiBase: string,
  headers: Record<string, string>,
): Promise<BillingStatus> {
  const r = await fetch(`${apiBase}/billing/sync`, {
    method: 'POST',
    headers: { ...headers, 'Content-Type': 'application/json' },
  })
  if (!r.ok) {
    const text = await r.text()
    throw new Error(text || `Billing sync failed (${r.status})`)
  }
  return r.json()
}

export async function confirmCheckoutSession(
  apiBase: string,
  headers: Record<string, string>,
  sessionId: string,
): Promise<BillingStatus> {
  const q = new URLSearchParams({ session_id: sessionId })
  const r = await fetch(`${apiBase}/billing/confirm?${q}`, { headers })
  if (!r.ok) {
    const text = await r.text()
    throw new Error(text || `Confirm checkout failed (${r.status})`)
  }
  await r.json()
  return fetchBillingStatus(apiBase, headers)
}
