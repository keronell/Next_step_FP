import { LogOut, Mail } from 'lucide-react'
import Eyebrow from './ui/Eyebrow.jsx'
import Button from './ui/Button.jsx'
import { useAuth } from '../contexts/AuthContext'

// Presentational account panel — the canonical, always-visible place a signed-in
// user sees their account details on the roadmap page. The header dropdown keeps a
// lightweight copy of the same info as a quick-access shortcut; both read from the
// same source (useAuth), so account-data fetching is not reimplemented here.
//
// Renders nothing when signed out, which preserves the page's gating: only a
// logged-in user ever sees the account panel (an anonymous deep-link still gets the
// roadmap, just no account card).
export default function AccountDetails({ onSignOut, className = '' }) {
  const { user, signOut } = useAuth()
  if (!user) return null

  const displayName = user.username || user.email
  const initial = (displayName || '?').trim().charAt(0).toUpperCase()

  const handleSignOut = async () => {
    await signOut()
    onSignOut?.()
  }

  return (
    <div className={`rounded-card bg-white border border-navy/[0.08] shadow-sm p-6 ${className}`}>
      <Eyebrow dot className="mb-4">Your Account</Eyebrow>

      <div className="flex items-center gap-3 mb-5">
        <div className="grid place-items-center h-11 w-11 rounded-full bg-gold/12 ring-1 ring-gold/30 shrink-0">
          <span className="font-display font-bold text-navy" aria-hidden="true">{initial}</span>
        </div>
        <div className="min-w-0">
          {user.username && (
            <p className="font-body text-body font-semibold text-navy truncate">
              {user.username}
            </p>
          )}
          <p className="font-body text-small text-navy/55 truncate inline-flex items-center gap-1.5">
            <Mail size={12} aria-hidden="true" className="text-navy/35 shrink-0" />
            {user.email}
          </p>
        </div>
      </div>

      <Button variant="secondary" size="md" onClick={handleSignOut} className="w-full">
        <LogOut size={15} aria-hidden="true" />
        Sign Out
      </Button>
    </div>
  )
}
