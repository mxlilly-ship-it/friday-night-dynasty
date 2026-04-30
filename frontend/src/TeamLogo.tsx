import { useEffect, useRef, useState } from 'react'
import { teamLogoUrl } from './logoUtils'
import './TeamLogo.css'
import { useLocalAssets } from './LocalAssetsContext'

type Props = {
  apiBase: string
  teamName: string
  logoVersion?: number
  headers?: Record<string, string>
  size?: number
  className?: string
  imgClassName?: string
  title?: string
}

/**
 * Loads `/saves/logos/{team}` with `fetch` + Bearer header (plain &lt;img&gt; cannot authenticate).
 */
export default function TeamLogo({
  apiBase,
  teamName,
  logoVersion,
  headers,
  size = 32,
  className = '',
  imgClassName = '',
  title,
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

    // Local bundle mode: render from in-memory logos (no fetch).
    const localLogo = localAssets?.getTeamLogo(teamName)
    if (localLogo) {
      revokeCurrent()
      const bytes = localLogo.data instanceof Uint8Array ? localLogo.data : new Uint8Array(localLogo.data as any)
      const ab = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength)
      const blob = new Blob([ab], { type: localLogo.mime || 'application/octet-stream' })
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
    const url = teamLogoUrl(apiBase, teamName, logoVersion)

    revokeCurrent()
    setBlobSrc(null)
    setMissing(false)

    ;(async () => {
      try {
        const r = await fetch(url, { headers })
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
  }, [apiBase, teamName, logoVersion, authSig, localAssets])

  if (!teamName?.trim()) {
    return (
      <span
        className={`teamlogo teamlogo-empty ${className}`}
        style={{ width: size, height: size }}
        title={title}
        aria-hidden
      />
    )
  }

  return (
    <span
      className={`teamlogo ${missing ? 'teamlogo-missing' : ''} ${className}`}
      style={{ width: size, height: size }}
      title={title ?? teamName}
    >
      {!missing && blobSrc ? (
        <img src={blobSrc} alt="" className={`teamlogo-img ${imgClassName}`} draggable={false} />
      ) : null}
    </span>
  )
}
