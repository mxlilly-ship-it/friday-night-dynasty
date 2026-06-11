import { createContext, useContext } from 'react'
import type { SaveBundle, SaveBundleAssetMap } from './saveBundle'

export type LocalAssets = {
  getTeamLogo: (teamName: string) => SaveBundleAssetMap[string] | null
  getTeamStadium: (teamName: string) => SaveBundleAssetMap[string] | null
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
          return bundle.logos?.[teamName] ?? null
        },
        getTeamStadium: (teamName: string) => {
          if (!teamName?.trim()) return null
          return bundle.stadiums?.[teamName] ?? null
        },
      }
    : null
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useLocalAssets(): LocalAssets | null {
  return useContext(Ctx)
}
