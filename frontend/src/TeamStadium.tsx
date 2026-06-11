import { useEffect, useRef, useState } from 'react'
import { useLocalAssets } from './LocalAssetsContext'
import { teamStadiumUrl } from './logoUtils'
import './TeamStadium.css'

type Props = {
  apiBase: string
  teamName: string
  stadiumVersion?: number
  headers?: Record<string, string>
  className?: string
  /** When true, omit the "No stadium photo yet" placeholder (e.g. parent shows its own fallback). */
  hidePlaceholder?: boolean
}

/**
 * Loads `/saves/stadiums/{team}` with fetch + Bearer (same auth pattern as {@link TeamLogo}).
 */
export default function TeamStadium({
  apiBase,
  teamName,
  stadiumVersion,
  headers,
  className = '',
  hidePlaceholder = false,
}: Props) {
  const [blobSrc, setBlobSrc] = useState<string | null>(null)
  const [missing, setMissing] = useState(false)
  const authSig = headers?.Authorization ?? ''
  const blobRef = useRef<string | null>(null)
  const localAssets = useLocalAssets()

  useEffect(() => {
    const revokeCurrent = () => {
      if (blobRef.current) {
        URL.revokeObjectURL(blobRef.current)
        blobRef.current = null
      }
    }

    if (!teamName?.trim()) {
      revokeCurrent()
      setBlobSrc(null)
      setMissing(false)
      return
    }

    const localStadium = localAssets?.getTeamStadium(teamName)
    if (localStadium) {
      revokeCurrent()
      const bytes =
        localStadium.data instanceof Uint8Array
          ? localStadium.data
          : new Uint8Array(localStadium.data as ArrayLike<number>)
      const blob = new Blob([bytes as BlobPart], { type: localStadium.mime || 'application/octet-stream' })
      const objUrl = URL.createObjectURL(blob)
      blobRef.current = objUrl
      setBlobSrc(objUrl)
      setMissing(false)
      return () => {
        revokeCurrent()
      }
    }

    if (!headers || !authSig) {
      revokeCurrent()
      setBlobSrc(null)
      setMissing(true)
      return
    }

    let cancelled = false
    const url = teamStadiumUrl(apiBase, teamName, stadiumVersion)

    revokeCurrent()
    setBlobSrc(null)
    setMissing(false)

    ;(async () => {
      try {
        const r = await fetch(url, { headers, cache: 'no-store' })
        if (!r.ok) {
          if (!cancelled) setMissing(true)
          return
        }
        const blob = await r.blob()
        const objUrl = URL.createObjectURL(blob)
        blobRef.current = objUrl
        if (!cancelled) {
          setBlobSrc(objUrl)
          setMissing(false)
        } else {
          URL.revokeObjectURL(objUrl)
        }
      } catch {
        if (!cancelled) setMissing(true)
      }
    })()

    return () => {
      cancelled = true
      revokeCurrent()
    }
  }, [apiBase, teamName, stadiumVersion, authSig, localAssets])

  if (!teamName?.trim()) {
    return <div className={`teamstadium teamstadium-empty ${className}`} aria-hidden />
  }

  return (
    <div className={['teamstadium', missing ? 'teamstadium-missing' : '', className].filter(Boolean).join(' ')}>
      {!missing && blobSrc ? (
        <img src={blobSrc} alt="" className="teamstadium-img" draggable={false} />
      ) : missing ? (
        hidePlaceholder ? null : (
          <div className="teamstadium-placeholder">No stadium photo yet</div>
        )
      ) : null}
    </div>
  )
}
