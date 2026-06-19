import { createContext, useContext } from 'react'

export type LogoPrefs = {
  /** Load crests from data/logos/ (built-in league). */
  preferDefaultLogos: boolean
  /** Cache-bust for default or save logo fetches. */
  logoVersion?: number
  saveId?: string
}

const Ctx = createContext<LogoPrefs | null>(null)

export function LogoPrefsProvider({
  value,
  children,
}: {
  value: LogoPrefs | null
  children: React.ReactNode
}) {
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useLogoPrefs(): LogoPrefs | null {
  return useContext(Ctx)
}
