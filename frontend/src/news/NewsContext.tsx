import { createContext, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { ingestStateNews, seedNewsFromSaveState } from './newsEngine'
import { getNewsCenter, type NewsCenter } from './newsStore'

type NewsContextValue = {
  center: NewsCenter
  saveId: string
  saveState: any
  selectedArticleId: string | null
  openArticle: (id: string) => void
  closeArticle: () => void
}

const NewsContext = createContext<NewsContextValue | null>(null)

export function NewsProvider({
  saveId,
  saveState,
  children,
}: {
  saveId: string
  saveState: any
  children: ReactNode
}) {
  const center = useMemo(() => getNewsCenter(saveId), [saveId])
  const [, setV] = useState(0)
  const [selectedArticleId, setSelectedArticleId] = useState<string | null>(null)

  useEffect(() => center.subscribe(() => setV((x) => x + 1)), [center])

  useEffect(() => {
    setSelectedArticleId(null)
  }, [saveId])

  const value = useMemo(
    (): NewsContextValue => ({
      center,
      saveId,
      saveState,
      selectedArticleId,
      openArticle: setSelectedArticleId,
      closeArticle: () => setSelectedArticleId(null),
    }),
    [center, saveId, saveState, selectedArticleId],
  )

  return <NewsContext.Provider value={value}>{children}</NewsContext.Provider>
}

export function useNews(): NewsContextValue {
  const v = useContext(NewsContext)
  if (!v) throw new Error('useNews must be used within NewsProvider')
  return v
}

function newsPruneKey(state: any): string {
  if (!state) return ''
  const w = state?.current_week
  const p = String(state?.season_phase ?? '').toLowerCase()
  const y = state?.current_year
  return `${y}|${p}|${w}`
}

export function NewsStateSync({ saveId, saveState, leagueHistory }: { saveId: string; saveState: any; leagueHistory?: any }) {
  const primed = useRef(false)
  const prev = useRef<any>(null)
  const lastPruneKey = useRef<string>('')
  const lastSaveId = useRef<string>('')

  useEffect(() => {
    if (!saveState || !saveId) return
    if (saveId !== lastSaveId.current) {
      lastSaveId.current = saveId
      lastPruneKey.current = ''
      primed.current = false
      prev.current = null
    }
    const center = getNewsCenter(saveId)
    const pkBody = newsPruneKey(saveState)
    const pk = `${saveId}:${pkBody}`
    if (pkBody && pk !== lastPruneKey.current) {
      lastPruneKey.current = pk
      center.pruneForState(saveState)
    }
    if (!primed.current) {
      primed.current = true
      prev.current = saveState
      seedNewsFromSaveState(saveState, saveId, leagueHistory)
      return
    }
    if (prev.current !== saveState) {
      ingestStateNews(prev.current, saveState, saveId, leagueHistory)
      prev.current = saveState
    }
  }, [saveState, saveId, leagueHistory])

  return null
}
