import { useEffect, useRef, useState } from 'react'
import { useLocalAssets } from './LocalAssetsContext'
import { teamHelmetUrl } from './logoUtils'
import './TeamUniformAsset.css'

type Props = {
  apiBase: string
  teamName: string
  helmetVersion?: number
  headers?: Record<string, string>
  className?: string
  hidePlaceholder?: boolean
}

export default function TeamHelmet({
  apiBase,
  teamName,
  helmetVersion,
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

    const localHelmet = localAssets?.getTeamHelmet(teamName)
    if (localHelmet) {
      revokeCurrent()
      const bytes =
        localHelmet.data instanceof Uint8Array
          ? localHelmet.data
          : new Uint8Array(localHelmet.data as ArrayLike<number>)
      const blob = new Blob([bytes as BlobPart], { type: localHelmet.mime || 'application/octet-stream' })
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
    const url = teamHelmetUrl(apiBase, teamName, helmetVersion)

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
  }, [apiBase, teamName, helmetVersion, authSig, localAssets])

  if (!teamName?.trim()) {
    return <div className={`teamuniformasset teamuniformasset-empty ${className}`} aria-hidden />
  }

  return (
    <div className={['teamuniformasset', missing ? 'teamuniformasset-missing' : '', className].filter(Boolean).join(' ')}>
      {!missing && blobSrc ? (
        <img src={blobSrc} alt="" className="teamuniformasset-img" draggable={false} />
      ) : missing ? (
        hidePlaceholder ? null : (
          <div className="teamuniformasset-placeholder">No helmet yet</div>
        )
      ) : null}
    </div>
  )
}
