import { useEffect, useRef, useState } from 'react'
import { teamDefaultLogoUrl, teamLogoUrl } from './logoUtils'
import './TeamLogo.css'
import { useLocalAssets } from './LocalAssetsContext'
import { useLogoPrefs } from './LogoPrefsContext'

type Props = {
  apiBase: string
  teamName: string
  logoVersion?: number
  headers?: Record<string, string>
  /** When set, skip fetch and show this URL (e.g. pending upload preview). */
  overrideSrc?: string | null
  /** Omit the crest slot entirely when no image loads (404 / no auth). */
  hideWhenMissing?: boolean
  /** Use data/logos/ built-in crests (new-save picker); skips user upload overrides. */
  preferDefaultLogos?: boolean
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
  overrideSrc,
  hideWhenMissing = false,
  preferDefaultLogos = false,
  size = 32,
  className = '',
  imgClassName = '',
  title,
}: Props) {
  const logoPrefs = useLogoPrefs()
  const useDefaultLogos = preferDefaultLogos || logoPrefs?.preferDefaultLogos || false
  const effectiveLogoVersion = logoVersion ?? logoPrefs?.logoVersion
  const effectiveSaveId = logoPrefs?.saveId
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

    if (overrideSrc) {
      revokeCurrent()
      setBlobSrc(overrideSrc)
      setMissing(false)
      return
    }

    // Local bundle mode: render from in-memory logos (no fetch).
    const localLogo = localAssets?.getTeamLogo(teamName)
    if (localLogo) {
      revokeCurrent()
      const bytes = localLogo.data instanceof Uint8Array ? localLogo.data : new Uint8Array(localLogo.data as ArrayLike<number>)
      const blob = new Blob([bytes as BlobPart], { type: localLogo.mime || 'application/octet-stream' })
      const objUrl = URL.createObjectURL(blob)
      blobRef.current = objUrl
      setBlobSrc(objUrl)
      setMissing(false)
      return () => {
        revokeCurrent()
      }
    }

    if (!headers || !authSig) {
      if (!useDefaultLogos) {
        revokeCurrent()
        setBlobSrc(null)
        setMissing(true)
        return
      }
    }

    let cancelled = false
    const url = useDefaultLogos
      ? teamDefaultLogoUrl(apiBase, teamName, effectiveLogoVersion)
      : teamLogoUrl(apiBase, teamName, effectiveLogoVersion, effectiveSaveId)

    revokeCurrent()
    setBlobSrc(null)
    setMissing(false)

    ;(async () => {
      try {
        const fetchHeaders: Record<string, string> = {}
        if (authSig) fetchHeaders.Authorization = headers!.Authorization!
        const r = await fetch(url, {
          headers: useDefaultLogos ? undefined : fetchHeaders,
          cache: 'no-store',
        })
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
  }, [apiBase, teamName, effectiveLogoVersion, effectiveSaveId, authSig, localAssets, overrideSrc, useDefaultLogos])

  if (!teamName?.trim()) {
    return hideWhenMissing ? null : (
      <span
        className={`teamlogo teamlogo-empty ${className}`}
        style={{ width: size, height: size }}
        title={title}
        aria-hidden
      />
    )
  }

  if (hideWhenMissing && missing && !blobSrc) {
    return null
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
