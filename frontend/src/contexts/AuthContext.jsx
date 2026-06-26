import { createContext, useContext, useEffect, useState } from 'react'
import { claimSessions, getMe, signIn as apiSignIn, signOut as apiSignOut, signUp as apiSignUp } from '../api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)      // { user_id, email } or null
  const [authLoading, setAuthLoading] = useState(true)

  // Rehydrate session from localStorage on mount.
  useEffect(() => {
    const token = localStorage.getItem('nextstep_access_token')
    if (!token) {
      setAuthLoading(false)
      return
    }
    getMe()
      .then(setUser)
      .catch(() => {
        localStorage.removeItem('nextstep_access_token')
        localStorage.removeItem('nextstep_refresh_token')
      })
      .finally(() => setAuthLoading(false))
  }, [])

  const _storeTokens = (data) => {
    localStorage.setItem('nextstep_access_token', data.access_token)
    localStorage.setItem('nextstep_refresh_token', data.refresh_token)
    setUser({ user_id: data.user_id, email: data.email })
  }

  const signUp = async (email, password) => {
    const data = await apiSignUp(email, password)
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

  return (
    <AuthContext.Provider value={{ user, authLoading, signUp, signIn, signOut }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within <AuthProvider>')
  return ctx
}
