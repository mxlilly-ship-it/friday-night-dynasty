import { useEffect, useMemo, useRef, useState } from 'react'
import { teamLogoUrl } from './logoUtils'
import { useLocalAssets } from './LocalAssetsContext'
import { renderPlayerCard } from './playerCard/playerCard.js'
import { buildPlayerCardData } from './playerCard/playerCardData'
import './playerCard/playerCard.css'
import './PlayerProfilePage.css'

type Props = {
  apiBase: string
  headers: Record<string, string>
  logoVersion: number
  teamName: string
  player: any
  saveState: any
  onClose: () => void
}

function usePlayerCardFonts() {
  useEffect(() => {
    if (!document.getElementById('pc-font-barlow')) {
      const preconnect = document.createElement('link')
      preconnect.rel = 'preconnect'
      preconnect.href = 'https://fonts.googleapis.com'
      document.head.appendChild(preconnect)
      const link = document.createElement('link')
      link.id = 'pc-font-barlow'
      link.rel = 'stylesheet'
      link.href =
        'https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@400;500;600;700&family=Barlow:wght@400;500;600&display=swap'
      document.head.appendChild(link)
    }
    if (!document.getElementById('pc-tabler-icons')) {
      const link = document.createElement('link')
      link.id = 'pc-tabler-icons'
      link.rel = 'stylesheet'
      link.href = 'https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@latest/tabler-icons.min.css'
      document.head.appendChild(link)
    }
  }, [])
}

export default function PlayerProfilePage({
  apiBase,
  headers,
  logoVersion,
  teamName,
  player,
  saveState,
  onClose,
}: Props) {
  usePlayerCardFonts()
  const cardRootRef = useRef<HTMLDivElement>(null)
  const localAssets = useLocalAssets()
  const [teamLogoSrc, setTeamLogoSrc] = useState<string | undefined>()

  useEffect(() => {
    let cancelled = false
    let objectUrl: string | null = null

    const localLogo = localAssets?.getTeamLogo(teamName)
    if (localLogo) {
      const bytes =
        localLogo.data instanceof Uint8Array ? localLogo.data : new Uint8Array(localLogo.data as ArrayLike<number>)
      const blob = new Blob([bytes as BlobPart], { type: localLogo.mime || 'application/octet-stream' })
      objectUrl = URL.createObjectURL(blob)
      setTeamLogoSrc(objectUrl)
      return () => {
        if (objectUrl) URL.revokeObjectURL(objectUrl)
      }
    }

    const url = teamLogoUrl(apiBase, teamName, logoVersion)
    const auth = headers?.Authorization
    fetch(url, auth ? { headers: { Authorization: auth } } : undefined)
      .then((r) => (r.ok ? r.blob() : null))
      .then((blob) => {
        if (cancelled || !blob) return
        objectUrl = URL.createObjectURL(blob)
        setTeamLogoSrc(objectUrl)
      })
      .catch(() => {
        if (!cancelled) setTeamLogoSrc(undefined)
      })

    return () => {
      cancelled = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [apiBase, teamName, headers, logoVersion, localAssets])

  const cardData = useMemo(
    () => buildPlayerCardData(player, teamName, saveState, { teamLogoSrc }),
    [player, teamName, saveState, teamLogoSrc],
  )

  useEffect(() => {
    if (!cardRootRef.current) return
    renderPlayerCard(cardData, cardRootRef.current)
  }, [cardData])

  return (
    <div className="player-profile">
      <div className="player-profile-top">
        <button type="button" className="player-profile-back" onClick={onClose}>
          ← Back
        </button>
      </div>
      <div className="player-profile-card-wrap">
        <div ref={cardRootRef} className="player-profile-card-root" />
      </div>
    </div>
  )
}
