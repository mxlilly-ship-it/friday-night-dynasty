import { useEffect, useRef, useState } from 'react'
import { useLocalAssets } from './LocalAssetsContext'
import { teamJerseyUrl, type JerseyKind } from './logoUtils'
import './TeamUniformAsset.css'

type Props = {
  apiBase: string
  teamName: string
  kind: JerseyKind
  jerseyVersion?: number
  headers?: Record<string, string>
  className?: string
  hidePlaceholder?: boolean
}

export default function TeamJersey({
  apiBase,
  teamName,
  kind,
  jerseyVersion,
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

    const localJersey = localAssets?.getTeamJersey(teamName, kind)
    if (localJersey) {
      revokeCurrent()
      const bytes =
        localJersey.data instanceof Uint8Array
          ? localJersey.data
          : new Uint8Array(localJersey.data as ArrayLike<number>)
      const blob = new Blob([bytes as BlobPart], { type: localJersey.mime || 'application/octet-stream' })
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
    const url = teamJerseyUrl(apiBase, teamName, kind, jerseyVersion)

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
  }, [apiBase, teamName, kind, jerseyVersion, authSig, localAssets])

  if (!teamName?.trim()) {
    return <div className={`teamuniformasset teamuniformasset-empty ${className}`} aria-hidden />
  }

  return (
    <div className={['teamuniformasset', missing ? 'teamuniformasset-missing' : '', className].filter(Boolean).join(' ')}>
      {!missing && blobSrc ? (
        <img src={blobSrc} alt="" className="teamuniformasset-img" draggable={false} />
      ) : missing ? (
        hidePlaceholder ? null : (
          <div className="teamuniformasset-placeholder">No jersey yet</div>
        )
      ) : null}
    </div>
  )
}
