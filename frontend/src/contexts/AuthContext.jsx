import { createContext, useContext, useEffect, useState } from 'react'
import { claimSessions, getMe, signIn as apiSignIn, signOut as apiSignOut, signUp as apiSignUp } from '../api'

const AuthContext = createContext(null)

// Privilege ordering — mirrors _ROLE_RANK in services/common/models/auth.py.
// Higher rank satisfies a lower-ranked gate (admin also passes a student gate).
// This is UX only; the backend re-checks every request and is the real gate.
const ROLE_RANK = { student: 0, admin: 100 }

export function roleAtLeast(userRole, required) {
  return (ROLE_RANK[userRole] ?? -1) >= (ROLE_RANK[required] ?? Infinity)
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)      // { user_id, email, username, role } or null
  const [authLoading, setAuthLoading] = useState(true)

  // Rehydrate session from localStorage on mount.
  useEffect(() => {
    const token = localStorage.getItem('nextstep_access_token')
    if (!token) {
      setAuthLoading(false)
      return
    }
    getMe()
      .then((u) => setUser({ ...u, role: u.role ?? 'student' }))
      .catch(() => {
        localStorage.removeItem('nextstep_access_token')
        localStorage.removeItem('nextstep_refresh_token')
      })
      .finally(() => setAuthLoading(false))
  }, [])

  const _storeTokens = (data) => {
    localStorage.setItem('nextstep_access_token', data.access_token)
    localStorage.setItem('nextstep_refresh_token', data.refresh_token)
    // role defaults to 'student' if an older backend omits it (DEV-62).
    setUser({
      user_id: data.user_id,
      email: data.email,
      username: data.username ?? '',
      role: data.role ?? 'student',
    })
  }

  const signUp = async (email, password, username) => {
    const data = await apiSignUp(email, password, username)
    _storeTokens(data)
    // Best-effort: link any prior anonymous submissions to the new account.
    claimSessions().catch(() => {})
    return data
  }

  const signIn = async (email, password) => {
    const data = await apiSignIn(email, password)
    _storeTokens(data)
    claimSessions().catch(() => {})
    return data
  }

  const signOut = async () => {
    // Always clear tokens locally even if the server call fails.
    try { await apiSignOut() } catch {} // eslint-disable-line no-empty
    localStorage.removeItem('nextstep_access_token')
    localStorage.removeItem('nextstep_refresh_token')
    setUser(null)
  }

  const role = user?.role ?? null
  const hasRole = (required) => !!user && roleAtLeast(user.role, required)

  return (
    <AuthContext.Provider
      value={{
        user,
        authLoading,
        signUp,
        signIn,
        signOut,
        role,
        isAdmin: hasRole('admin'),
        hasRole,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within <AuthProvider>')
  return ctx
}
