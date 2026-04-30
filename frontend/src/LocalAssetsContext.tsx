import { createContext, useContext } from 'react'
import type { SaveBundle } from './saveBundle'

export type LocalAssets = {
  getTeamLogo: (teamName: string) => { filename: string; data: Uint8Array; mime: string } | null
}

const Ctx = createContext<LocalAssets | null>(null)

export function LocalAssetsProvider({
  bundle,
  children,
}: {
  bundle: SaveBundle | null
  children: React.ReactNode
}) {
  const value: LocalAssets | null = bundle
    ? {
        getTeamLogo: (teamName: string) => {
          if (!teamName?.trim()) return null
          const hit = bundle.logos?.[teamName]
          return hit ?? null
        },
      }
    : null
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useLocalAssets(): LocalAssets | null {
  return useContext(Ctx)
}

