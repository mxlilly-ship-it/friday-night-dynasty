import JSZip from 'jszip'
import { suggestTeamForLogoFilename } from './logoMatch'

export type SaveBundle = {
  state: any
  leagueHistory: any
  records: any
  /**
   * key: normalized team name (exact match used elsewhere in UI)
   * value: { filename, data, mime }
   */
  logos: Record<string, { filename: string; data: Uint8Array; mime: string }>
  /** Optional recap text files (path -> text) */
  seasonRecaps: Record<string, string>
}

function guessMime(filename: string): string {
  const low = filename.toLowerCase()
  if (low.endsWith('.png')) return 'image/png'
  if (low.endsWith('.jpg') || low.endsWith('.jpeg')) return 'image/jpeg'
  if (low.endsWith('.webp')) return 'image/webp'
  return 'application/octet-stream'
}

function safeJsonParse(text: string, label: string) {
  try {
    return JSON.parse(text)
  } catch (e: any) {
    throw new Error(`Invalid JSON in ${label}`)
  }
}

export async function importSaveZip(file: File): Promise<SaveBundle> {
  const zip = await JSZip.loadAsync(file)

  const getText = async (path: string) => {
    const entry = zip.file(path)
    if (!entry) return null
    return await entry.async('text')
  }

  const stateText = (await getText('league_save.json')) ?? (await getText('./league_save.json'))
  if (!stateText) throw new Error('Missing league_save.json in zip')
  const state = safeJsonParse(stateText, 'league_save.json')

  const histText = (await getText('league_history.json')) ?? (await getText('./league_history.json'))
  const leagueHistory = histText ? safeJsonParse(histText, 'league_history.json') : { seasons: [] }

  const recordsText = (await getText('records.json')) ?? (await getText('./records.json'))
  const records = recordsText ? safeJsonParse(recordsText, 'records.json') : {}

  const logos: SaveBundle['logos'] = {}
  const seasonRecaps: SaveBundle['seasonRecaps'] = {}
  const teamNames = Array.isArray(state?.teams) ? state.teams.map((t: any) => String(t?.name ?? '')).filter(Boolean) : []

  const files = Object.keys(zip.files)
  for (const p of files) {
    const entry = zip.files[p]
    if (!entry || entry.dir) continue
    const norm = p.replace(/\\/g, '/')
    if (norm.toLowerCase().startsWith('logos/')) {
      const filename = norm.split('/').pop() || norm
      const data = await entry.async('uint8array')
      const guess = teamNames.length ? suggestTeamForLogoFilename(filename, teamNames) : ''
      const key = guess || filename.replace(/\.[^.]+$/, '')
      logos[key] = { filename, data, mime: guessMime(filename) }
    } else if (norm.toLowerCase().startsWith('season_recaps/') && norm.toLowerCase().endsWith('.txt')) {
      seasonRecaps[norm] = await entry.async('text')
    }
  }

  return { state, leagueHistory, records, logos, seasonRecaps }
}

export async function exportSaveZip(bundle: SaveBundle): Promise<Blob> {
  const zip = new JSZip()
  zip.file('league_save.json', JSON.stringify(bundle.state ?? {}, null, 2))
  zip.file('league_history.json', JSON.stringify(bundle.leagueHistory ?? { seasons: [] }, null, 2))
  zip.file('records.json', JSON.stringify(bundle.records ?? {}, null, 2))

  for (const [team, logo] of Object.entries(bundle.logos ?? {})) {
    const fn = logo.filename || `${team}.png`
    zip.file(`logos/${fn}`, logo.data)
  }

  for (const [path, text] of Object.entries(bundle.seasonRecaps ?? {})) {
    zip.file(path, text ?? '')
  }

  return await zip.generateAsync({ type: 'blob' })
}

