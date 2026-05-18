import { useEffect, useRef, useState } from 'react'
import { teamStadiumUrl } from './logoUtils'
import './TeamStadium.css'

type Props = {
  apiBase: string
  teamName: string
  stadiumVersion?: number
  headers?: Record<string, string>
  className?: string
}

/**
 * Loads `/saves/stadiums/{team}` with fetch + Bearer (same auth pattern as {@link TeamLogo}).
 */
export default function TeamStadium({ apiBase, teamName, stadiumVersion, headers, className = '' }: Props) {
  const [blobSrc, setBlobSrc] = useState<string | null>(null)
  const [missing, setMissing] = useState(false)
  const authSig = headers?.Authorization ?? ''
  const blobRef = useRef<string | null>(null)

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
  }, [apiBase, teamName, stadiumVersion, authSig])

  if (!teamName?.trim()) {
    return <div className={`teamstadium teamstadium-empty ${className}`} aria-hidden />
  }

  return (
    <div className={['teamstadium', missing ? 'teamstadium-missing' : '', className].filter(Boolean).join(' ')}>
      {!missing && blobSrc ? (
        <img src={blobSrc} alt="" className="teamstadium-img" draggable={false} />
      ) : missing ? (
        <div className="teamstadium-placeholder">No stadium photo yet</div>
      ) : null}
    </div>
  )
}
