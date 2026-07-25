import { useCallback, useEffect, useState } from 'react'
import { ArrowLeft, Loader2, Trash2 } from 'lucide-react'
import { fetchAccounts, deleteAccount } from '../api'
import { useAuth } from '../contexts/AuthContext'
import { navigate, replaceWithHome } from '../hooks/useRoute'

// DEV-62: the app's only privileged screen. `require_admin` on the server is the
// real gate — this page hiding itself is presentation, and a non-admin who types
// the URL gets 403s from the API either way.

// Explicit color-mix, NOT `bg-navy/[0.04]`: the theme tokens are plain CSS-var
// strings with no <alpha-value>, so Tailwind drops opacity-modified declarations
// silently (frontend/CLAUDE.md). Same workaround the roadmap canvas uses.
const HAIRLINE = 'color-mix(in srgb, var(--color-navy) 8%, transparent)'
const SKELETON = 'color-mix(in srgb, var(--color-navy) 4%, transparent)'

// Mirrors ADMIN_LIST_LIMIT in services/auth/app/services/auth_service.py — used
// only to caption a full page, never to slice the response.
const ACCOUNT_LIST_CAP = 100

function formatDate(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString(undefined, {
    year: 'numeric', month: 'short', day: 'numeric',
  })
}

export default function Admin() {
  const { user, authLoading } = useAuth()
  const [accounts, setAccounts] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [busyId, setBusyId] = useState(null)

  const isAdmin = user?.role === 'admin'

  // Bounce non-admins home — but only once auth has RESOLVED. On a cold load of
  // /admin, `user` is null while getMe() is still in flight, so redirecting on
  // !user alone would throw an admin off their own page on every refresh.
  useEffect(() => {
    if (!authLoading && !isAdmin) replaceWithHome()
  }, [authLoading, isAdmin])

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setAccounts(await fetchAccounts())
    } catch (err) {
      setError(err?.status === 403 ? 'Admin access required.' : 'Could not load accounts.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (isAdmin) load()
  }, [isAdmin, load])

  const handleDelete = async (account) => {
    // Native confirm: deletion is irreversible and cascades the account's profile.
    if (!window.confirm(
      `Delete ${account.email}? Their account and profile are removed permanently.`
    )) return
    setBusyId(account.user_id)
    setError(null)
    try {
      await deleteAccount(account.user_id)
      await load()  // refetch rather than filter: the list is capped server-side
    } catch (err) {
      // Only a string detail is renderable — a 422 body's detail is an array of
      // objects, which React would throw on.
      const detail = err?.body?.detail
      setError(typeof detail === 'string' ? detail : 'Could not delete that account.')
    } finally {
      setBusyId(null)
    }
  }

  if (authLoading || !isAdmin) {
    return (
      <div className="min-h-screen bg-cream flex items-center justify-center" role="status" aria-label="Loading">
        <Loader2 size={22} className="text-navy/30 animate-spin" aria-hidden="true" />
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-cream">
      <main className="max-w-4xl mx-auto px-6 py-16">
        <button
          onClick={() => navigate('/')}
          className="focus-ring flex items-center gap-2 font-body text-small text-navy/55 hover:text-navy transition-colors duration-fast"
        >
          <ArrowLeft size={15} aria-hidden="true" />
          Back to home
        </button>

        <h1 className="font-display text-h1 text-navy mt-6">Accounts</h1>
        <p className="font-body text-small text-navy/55 mt-2">
          Deleting an account removes its sign-in and profile permanently.
          {/* The server returns one page (ADMIN_LIST_LIMIT). Say so when we're
              sitting on it, rather than presenting a truncated list as complete. */}
          {accounts.length >= ACCOUNT_LIST_CAP && ` Showing the ${ACCOUNT_LIST_CAP} newest accounts.`}
        </p>

        {error && (
          <p className="font-body text-small text-red-600 mt-6" role="alert">{error}</p>
        )}

        {loading && (
          <div className="flex flex-col gap-2 mt-8">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-14 rounded-xl animate-pulse" style={{ background: SKELETON }} />
            ))}
          </div>
        )}

        {!loading && accounts.length === 0 && !error && (
          <p className="font-body text-small text-navy/55 mt-8">No accounts yet.</p>
        )}

        {!loading && accounts.length > 0 && (
          <div className="mt-8 overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b" style={{ borderColor: HAIRLINE }}>
                  {['Email', 'Username', 'Role', 'Joined', ''].map((h) => (
                    <th key={h} scope="col" className="font-body text-eyebrow text-navy/40 uppercase font-semibold py-3 pr-4">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {accounts.map((a) => {
                  const isSelf = a.user_id === user.user_id
                  return (
                    <tr key={a.user_id} className="border-b" style={{ borderColor: HAIRLINE }}>
                      <td className="font-body text-small text-navy py-3 pr-4">
                        {a.email}
                        {isSelf && <span className="text-navy/40"> (you)</span>}
                      </td>
                      <td className="font-body text-small text-navy/70 py-3 pr-4">{a.username || '—'}</td>
                      <td className="font-body text-small text-navy/70 py-3 pr-4">{a.role}</td>
                      <td className="font-body text-small text-navy/55 py-3 pr-4">{formatDate(a.created_at)}</td>
                      <td className="py-3 text-right">
                        {/* No delete on your own row: the server rejects it with a 400,
                            and the role can only be restored in SQL. */}
                        {!isSelf && (
                          <button
                            onClick={() => handleDelete(a)}
                            disabled={busyId === a.user_id}
                            aria-label={`Delete ${a.email}`}
                            className="focus-ring p-2 rounded-lg text-navy/40 hover:text-red-600 transition-colors duration-fast disabled:opacity-40"
                          >
                            {busyId === a.user_id
                              ? <Loader2 size={15} className="animate-spin" aria-hidden="true" />
                              : <Trash2 size={15} aria-hidden="true" />}
                          </button>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </div>
  )
}
