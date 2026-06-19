import { useEffect, useRef, useState } from 'react'
import { useLocalAssets } from './LocalAssetsContext'
import { defaultStadiumUrl, teamStadiumUrl } from './logoUtils'
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

async function loadImageBlob(url: string, headers?: Record<string, string>): Promise<Blob | null> {
  try {
    const r = await fetch(url, {
      headers: headers ?? undefined,
      cache: 'no-store',
    })
    if (!r.ok) return null
    return await r.blob()
  } catch {
    return null
  }
}

/**
 * Loads custom `/saves/stadiums/{team}` when present, otherwise the built-in default stadium photo.
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

    const setFromBlob = (blob: Blob) => {
      revokeCurrent()
      const objUrl = URL.createObjectURL(blob)
      blobRef.current = objUrl
      setBlobSrc(objUrl)
      setMissing(false)
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
      setFromBlob(blob)
      return () => {
        revokeCurrent()
      }
    }

    let cancelled = false
    revokeCurrent()
    setBlobSrc(null)
    setMissing(false)

    ;(async () => {
      let blob: Blob | null = null

      if (headers && authSig) {
        blob = await loadImageBlob(teamStadiumUrl(apiBase, teamName, stadiumVersion), headers)
      }

      if (!blob) {
        blob = await loadImageBlob(defaultStadiumUrl(apiBase, stadiumVersion))
      }

      if (cancelled) return

      if (blob) {
        setFromBlob(blob)
      } else {
        revokeCurrent()
        setBlobSrc(null)
        setMissing(true)
      }
    })()

    return () => {
      cancelled = true
      revokeCurrent()
    }
  }, [apiBase, teamName, stadiumVersion, authSig, localAssets, headers])

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
