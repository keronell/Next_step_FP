import { useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Eye, EyeOff, Lock, Mail, X } from 'lucide-react'
import Button from '../components/ui/Button.jsx'
import { useAuth } from '../contexts/AuthContext'

export default function AuthModal({ open, onClose }) {
  const { signIn, signUp } = useAuth()

  const [mode, setMode] = useState('signin')   // 'signin' | 'signup'
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const emailRef = useRef(null)

  // Focus email input when modal opens
  useEffect(() => {
    if (open) {
      setError(null)
      setTimeout(() => emailRef.current?.focus(), 80)
    }
  }, [open])

  // Clear error + password when switching modes
  const switchMode = (next) => {
    setMode(next)
    setError(null)
    setPassword('')
    setShowPassword(false)
  }

  // Close on Escape
  useEffect(() => {
    if (!open) return
    const handler = (e) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [open, onClose])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      if (mode === 'signin') {
        await signIn(email, password)
      } else {
        await signUp(email, password)
      }
      onClose()
    } catch (err) {
      const detail = err.body?.detail
      if (typeof detail === 'string') {
        setError(detail)
      } else if (Array.isArray(detail)) {
        // FastAPI 422 validation error — extract the first human-readable message
        setError(detail[0]?.msg || 'Please check your email and password.')
      } else if (err.status === 503) {
        setError('Authentication is temporarily unavailable.')
      } else if (!err.status) {
        // fetch() threw before getting a response (network/CORS failure)
        setError('Could not reach the server. Is the backend running?')
      } else {
        setError('Something went wrong. Please try again.')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop — sits above header (z-50) */}
          <motion.div
            key="auth-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 z-[100] bg-navy/50 backdrop-blur-sm"
            onClick={onClose}
            aria-hidden="true"
          />

          {/* Modal card */}
          <motion.div
            key="auth-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="auth-modal-title"
            initial={{ opacity: 0, y: 32, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 16, scale: 0.98 }}
            transition={{ type: 'spring', stiffness: 340, damping: 30 }}
            className="fixed left-4 right-4 top-[10vh] z-[101] sm:left-1/2 sm:right-auto sm:-translate-x-1/2 sm:w-[440px] bg-white rounded-card shadow-2xl border border-navy/[0.08] overflow-hidden"
          >
            {/* Gold accent bar */}
            <div className="h-1 bg-gradient-to-r from-gold to-gold-light" />

            <div className="p-8">
              {/* Header row */}
              <div className="flex items-start justify-between mb-6">
                <div>
                  <p className="font-display font-bold text-base text-navy leading-tight">
                    The Next Step
                  </p>
                  <p className="font-body text-eyebrow font-medium text-gold uppercase leading-tight mt-0.5">
                    Career Discovery
                  </p>
                </div>
                <button
                  onClick={onClose}
                  aria-label="Close"
                  className="focus-ring p-2 rounded-full text-navy/40 hover:text-navy hover:bg-navy/[0.06] transition-all duration-fast"
                >
                  <X size={18} aria-hidden="true" />
                </button>
              </div>

              {/* Tab switcher */}
              <div className="flex mb-7 rounded-xl bg-cream p-1 gap-1">
                {[
                  { key: 'signin', label: 'Sign In' },
                  { key: 'signup', label: 'Create Account' },
                ].map(({ key, label }) => (
                  <button
                    key={key}
                    type="button"
                    onClick={() => switchMode(key)}
                    className={[
                      'flex-1 py-2 px-3 rounded-lg font-body text-small font-semibold transition-all duration-base',
                      mode === key
                        ? 'bg-white text-navy shadow-sm ring-1 ring-inset ring-navy/[0.07]'
                        : 'text-navy/55 hover:text-navy',
                    ].join(' ')}
                  >
                    {label}
                  </button>
                ))}
              </div>

              {/* Form */}
              <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">

                {/* Email field */}
                <div className="flex flex-col gap-1.5">
                  <label htmlFor="auth-email" className="font-body text-small font-medium text-navy/70">
                    Email
                  </label>
                  <div className="relative">
                    <Mail
                      size={15}
                      aria-hidden="true"
                      className="absolute left-3.5 top-1/2 -translate-y-1/2 text-navy/35 pointer-events-none"
                    />
                    <input
                      ref={emailRef}
                      id="auth-email"
                      type="email"
                      autoComplete="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="you@example.com"
                      required
                      className="w-full pl-10 pr-4 py-3 rounded-xl border border-navy/[0.14] bg-cream/60 font-body text-body text-navy placeholder:text-navy/35 focus:outline-none focus:ring-2 focus:ring-gold/50 focus:border-gold/60 transition-all duration-base"
                    />
                  </div>
                </div>

                {/* Password field */}
                <div className="flex flex-col gap-1.5">
                  <label htmlFor="auth-password" className="font-body text-small font-medium text-navy/70">
                    Password
                    {mode === 'signup' && (
                      <span className="ml-1 font-normal text-navy/40">(min. 8 characters)</span>
                    )}
                  </label>
                  <div className="relative">
                    <Lock
                      size={15}
                      aria-hidden="true"
                      className="absolute left-3.5 top-1/2 -translate-y-1/2 text-navy/35 pointer-events-none"
                    />
                    <input
                      id="auth-password"
                      type={showPassword ? 'text' : 'password'}
                      autoComplete={mode === 'signup' ? 'new-password' : 'current-password'}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="••••••••"
                      required
                      minLength={mode === 'signup' ? 8 : undefined}
                      className="w-full pl-10 pr-11 py-3 rounded-xl border border-navy/[0.14] bg-cream/60 font-body text-body text-navy placeholder:text-navy/35 focus:outline-none focus:ring-2 focus:ring-gold/50 focus:border-gold/60 transition-all duration-base"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword((v) => !v)}
                      aria-label={showPassword ? 'Hide password' : 'Show password'}
                      className="focus-ring absolute right-3 top-1/2 -translate-y-1/2 p-1 rounded text-navy/35 hover:text-navy/70 transition-colors duration-fast"
                    >
                      {showPassword
                        ? <EyeOff size={15} aria-hidden="true" />
                        : <Eye size={15} aria-hidden="true" />}
                    </button>
                  </div>
                </div>

                {/* Inline error */}
                <AnimatePresence>
                  {error && (
                    <motion.p
                      key="auth-error"
                      initial={{ opacity: 0, height: 0, marginTop: -8 }}
                      animate={{ opacity: 1, height: 'auto', marginTop: 0 }}
                      exit={{ opacity: 0, height: 0, marginTop: -8 }}
                      transition={{ duration: 0.2 }}
                      role="alert"
                      className="font-body text-small text-red-700 bg-red-50 border border-red-200 rounded-xl px-4 py-3 leading-snug"
                    >
                      {error}
                    </motion.p>
                  )}
                </AnimatePresence>

                {/* Submit */}
                <Button
                  as="button"
                  type="submit"
                  variant="primary"
                  size="md"
                  loading={loading}
                  className="w-full mt-1"
                >
                  {mode === 'signin' ? 'Sign In' : 'Create Account'}
                </Button>
              </form>

              {/* Footer toggle */}
              <p className="mt-5 text-center font-body text-small text-navy/55">
                {mode === 'signin' ? (
                  <>
                    No account?{' '}
                    <button
                      type="button"
                      onClick={() => switchMode('signup')}
                      className="focus-ring text-gold font-semibold hover:text-gold/80 transition-colors duration-fast"
                    >
                      Create one
                    </button>
                  </>
                ) : (
                  <>
                    Already have an account?{' '}
                    <button
                      type="button"
                      onClick={() => switchMode('signin')}
                      className="focus-ring text-gold font-semibold hover:text-gold/80 transition-colors duration-fast"
                    >
                      Sign in
                    </button>
                  </>
                )}
              </p>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
