export type LeagueStartType = 'default' | 'custom' | 'help'

export const LEAGUE_START_TYPES: { id: LeagueStartType; label: string; hint: string }[] = [
  {
    id: 'default',
    label: 'Built-in default teams',
    hint: 'Use the standard 112-school league file shipped with FND.',
  },
  {
    id: 'custom',
    label: 'Custom teams file',
    hint: 'Upload your own teams.json league file.',
  },
  {
    id: 'help',
    label: 'Not sure yet',
    hint: 'We can help you pick the right league setup.',
  },
]

export const US_STATES = [
  'Alabama',
  'Alaska',
  'Arizona',
  'Arkansas',
  'California',
  'Colorado',
  'Connecticut',
  'Delaware',
  'District of Columbia',
  'Florida',
  'Georgia',
  'Hawaii',
  'Idaho',
  'Illinois',
  'Indiana',
  'Iowa',
  'Kansas',
  'Kentucky',
  'Louisiana',
  'Maine',
  'Maryland',
  'Massachusetts',
  'Michigan',
  'Minnesota',
  'Mississippi',
  'Missouri',
  'Montana',
  'Nebraska',
  'Nevada',
  'New Hampshire',
  'New Jersey',
  'New Mexico',
  'New York',
  'North Carolina',
  'North Dakota',
  'Ohio',
  'Oklahoma',
  'Oregon',
  'Pennsylvania',
  'Rhode Island',
  'South Carolina',
  'South Dakota',
  'Tennessee',
  'Texas',
  'Utah',
  'Vermont',
  'Virginia',
  'Washington',
  'West Virginia',
  'Wisconsin',
  'Wyoming',
]

export type LeagueStartRequestPayload = {
  league_type: LeagueStartType
  estimated_players: number
  state: string
  contact_email?: string
  notes?: string
  league_file?: File | null
}

export async function submitLeagueStartRequest(
  apiBase: string,
  payload: LeagueStartRequestPayload,
  headers: Record<string, string> = {},
): Promise<{ request_id: string; message: string; email_sent?: boolean }> {
  const form = new FormData()
  form.append('league_type', payload.league_type)
  form.append('estimated_players', String(payload.estimated_players))
  form.append('state', payload.state)
  if (payload.contact_email?.trim()) {
    form.append('contact_email', payload.contact_email.trim())
  }
  if (payload.notes?.trim()) {
    form.append('notes', payload.notes.trim())
  }
  if (payload.league_file) {
    form.append('league_file', payload.league_file, payload.league_file.name)
  }

  const authHeaders = { ...headers }
  delete authHeaders['Content-Type']
  delete authHeaders['content-type']

  const r = await fetch(`${apiBase}/leagues/start-requests`, {
    method: 'POST',
    headers: authHeaders,
    body: form,
  })
  const text = await r.text()
  let data: { request_id?: string; message?: string; email_sent?: boolean; detail?: unknown } | null = null
  try {
    data = text ? JSON.parse(text) : null
  } catch {
    data = null
  }
  if (!r.ok) {
    const detail = data?.detail
    throw new Error(typeof detail === 'string' ? detail : text || `Request failed (${r.status})`)
  }
  return {
    request_id: String(data?.request_id ?? ''),
    message: String(data?.message ?? 'Request sent.'),
    email_sent: Boolean(data?.email_sent),
  }
}
