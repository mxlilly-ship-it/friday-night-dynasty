/**
 * Tip jar / donation link on the title screen.
 * Override at build time with VITE_TIP_JAR_URL if needed.
 */
const FALLBACK_TIP_JAR_URL = 'https://buy.stripe.com/eVqcN6bRm6fa2ET4S3aZi01'

export const TIP_JAR_URL = String(
  (import.meta as ImportMeta & { env?: { VITE_TIP_JAR_URL?: string } }).env?.VITE_TIP_JAR_URL ||
    FALLBACK_TIP_JAR_URL,
).trim()
