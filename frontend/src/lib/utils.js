import { clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

/**
 * Merge conditional class names and resolve Tailwind conflicts.
 * Used by all ported 21st.dev components.
 */
export function cn(...inputs) {
  return twMerge(clsx(inputs))
}
