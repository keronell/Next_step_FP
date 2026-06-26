import { useEffect, useRef, useState } from 'react'
import { ChevronDown, Clock, LogOut, Menu, Sparkles, X } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import Button from './ui/Button.jsx'
import { useAuth } from '../contexts/AuthContext'

function Header({ phase, onReset, onOpenAuth }) {
  const { user, authLoading, signOut } = useAuth()

  const [menuOpen, setMenuOpen] = useState(false)
  const [scrolled, setScrolled] = useState(false)
  const [hovered, setHovered] = useState(null)
  const [accountOpen, setAccountOpen] = useState(false)
  const accountRef = useRef(null)

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24)
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  // Close account dropdown on outside click
  useEffect(() => {
    if (!accountOpen) return
    const handler = (e) => {
      if (accountRef.current && !accountRef.current.contains(e.target)) {
        setAccountOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [accountOpen])

  const scrollToSection = (id) => {
    setMenuOpen(false)
    setAccountOpen(false)
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  const handleSignOut = async () => {
    setAccountOpen(false)
    setMenuOpen(false)
    await signOut()
  }

  const navItems = [
    { label: 'Home', id: 'hero' },
    { label: 'How It Works', id: 'how-it-works' },
    { label: 'Assessment', id: 'assessment' },
    ...(phase === 'results_ready' ? [{ label: 'Results', id: 'results' }] : []),
  ]

  // Truncate email for display
  const displayEmail = user?.email
    ? user.email.length > 22 ? user.email.slice(0, 20) + '…' : user.email
    : ''

  return (
    <>
      <header className="sticky top-0 z-50 px-3">
        <motion.div
          initial={false}
          animate={{
            maxWidth: scrolled ? 880 : 1152,
            marginTop: scrolled ? 12 : 0,
            borderRadius: scrolled ? 9999 : 0,
            backgroundColor: scrolled ? 'rgba(250,247,242,0.85)' : 'rgba(250,247,242,0)',
            boxShadow: scrolled
              ? '0 10px 40px -12px rgba(15,27,45,0.25), inset 0 0 0 1px rgba(201,168,76,0.18)'
              : '0 0 0 0 rgba(0,0,0,0)',
          }}
          transition={{ type: 'spring', stiffness: 220, damping: 32 }}
          className="mx-auto backdrop-blur-md"
        >
          <div className="px-5 sm:px-6 h-16 flex items-center justify-between">
            {/* Logo */}
            <button
              onClick={onReset}
              className="focus-ring flex flex-col items-start group rounded-md px-1 py-0.5"
            >
              <span className="font-display font-bold text-xl text-navy group-hover:text-gold transition-colors duration-fast leading-none">
                The Next Step
              </span>
              <span className="font-body text-eyebrow font-medium text-gold uppercase leading-none mt-1">
                Career Discovery
              </span>
            </button>

            {/* Desktop nav */}
            <nav
              className="hidden md:flex items-center gap-1"
              onMouseLeave={() => setHovered(null)}
            >
              {navItems.map((item) => (
                <button
                  key={item.id}
                  onClick={() => scrollToSection(item.id)}
                  onMouseEnter={() => setHovered(item.id)}
                  className="focus-ring relative px-4 py-2 rounded-full font-body text-small text-navy/75 hover:text-navy transition-colors duration-fast"
                >
                  {hovered === item.id && (
                    <motion.span
                      layoutId="nav-pill"
                      className="absolute inset-0 rounded-full bg-gold/12 ring-1 ring-inset ring-gold/25"
                      transition={{ type: 'spring', stiffness: 380, damping: 30 }}
                    />
                  )}
                  <span className="relative z-10">{item.label}</span>
                </button>
              ))}

              {/* Auth controls */}
              {!authLoading && !user && (
                <button
                  onClick={onOpenAuth}
                  className="focus-ring relative px-4 py-2 rounded-full font-body text-small text-navy/75 hover:text-navy transition-colors duration-fast"
                >
                  Sign In
                </button>
              )}

              {!authLoading && user && (
                <div ref={accountRef} className="relative ml-1">
                  <button
                    onClick={() => setAccountOpen((v) => !v)}
                    className="focus-ring flex items-center gap-1.5 px-4 py-2 rounded-full font-body text-small text-navy/75 hover:text-navy transition-colors duration-fast"
                  >
                    <span className="max-w-[120px] truncate">{displayEmail}</span>
                    <motion.span
                      animate={{ rotate: accountOpen ? 180 : 0 }}
                      transition={{ duration: 0.2 }}
                    >
                      <ChevronDown size={13} aria-hidden="true" />
                    </motion.span>
                  </button>

                  <AnimatePresence>
                    {accountOpen && (
                      <motion.div
                        initial={{ opacity: 0, y: -6, scale: 0.97 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        exit={{ opacity: 0, y: -6, scale: 0.97 }}
                        transition={{ duration: 0.15 }}
                        className="absolute right-0 top-full mt-2 w-52 bg-white rounded-2xl border border-navy/[0.08] shadow-lg py-2 z-10"
                      >
                        <div className="px-4 py-2 border-b border-navy/[0.06]">
                          <p className="font-body text-eyebrow text-navy/40 uppercase font-semibold">Signed in as</p>
                          <p className="font-body text-small text-navy font-medium truncate mt-0.5">{user.email}</p>
                        </div>
                        <button
                          onClick={() => scrollToSection('history')}
                          className="focus-ring w-full text-left flex items-center gap-2.5 px-4 py-2.5 font-body text-small text-navy/70 hover:text-navy hover:bg-navy/[0.04] transition-colors duration-fast"
                        >
                          <Clock size={14} aria-hidden="true" className="text-navy/40" />
                          My History
                        </button>
                        <button
                          onClick={handleSignOut}
                          className="focus-ring w-full text-left flex items-center gap-2.5 px-4 py-2.5 font-body text-small text-navy/70 hover:text-navy hover:bg-navy/[0.04] transition-colors duration-fast"
                        >
                          <LogOut size={14} aria-hidden="true" className="text-navy/40" />
                          Sign Out
                        </button>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              )}

              <Button
                variant="primary"
                size="md"
                onClick={() => scrollToSection('assessment')}
                className="ml-2 !px-5 !py-2 !text-small"
              >
                <Sparkles size={14} aria-hidden="true" />
                Start Assessment
              </Button>
            </nav>

            {/* Mobile hamburger */}
            <button
              className="focus-ring md:hidden p-2 rounded-md text-navy hover:text-gold transition-colors duration-fast"
              onClick={() => setMenuOpen(!menuOpen)}
              aria-label="Toggle menu"
              aria-expanded={menuOpen}
            >
              {menuOpen ? <X size={22} aria-hidden="true" /> : <Menu size={22} aria-hidden="true" />}
            </button>
          </div>
        </motion.div>

        {/* Mobile dropdown */}
        <AnimatePresence>
          {menuOpen && (
            <motion.div
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.2 }}
              className="md:hidden mx-auto mt-2 max-w-6xl rounded-2xl bg-cream/95 backdrop-blur-md border border-gold/20 shadow-lg px-6 py-4 flex flex-col gap-1"
            >
              {navItems.map((item) => (
                <button
                  key={item.id}
                  onClick={() => scrollToSection(item.id)}
                  className="focus-ring text-left font-body text-navy/80 hover:text-gold py-2.5 border-b border-navy/5 last:border-0 transition-colors duration-fast"
                >
                  {item.label}
                </button>
              ))}

              <Button
                variant="primary"
                size="md"
                onClick={() => scrollToSection('assessment')}
                className="mt-3 !text-small"
              >
                <Sparkles size={14} aria-hidden="true" />
                Start Assessment
              </Button>

              {/* Auth section in mobile menu */}
              {!authLoading && !user && (
                <button
                  onClick={() => { setMenuOpen(false); onOpenAuth() }}
                  className="focus-ring mt-2 text-left font-body text-small text-navy/60 hover:text-gold transition-colors duration-fast py-2"
                >
                  Sign In to save your results
                </button>
              )}

              {!authLoading && user && (
                <div className="mt-2 pt-3 border-t border-navy/[0.06] flex flex-col gap-1">
                  <p className="font-body text-eyebrow text-navy/40 uppercase font-semibold px-0.5 mb-1">
                    {user.email}
                  </p>
                  <button
                    onClick={() => scrollToSection('history')}
                    className="focus-ring flex items-center gap-2 text-left font-body text-small text-navy/65 hover:text-gold transition-colors duration-fast py-2"
                  >
                    <Clock size={13} aria-hidden="true" />
                    My History
                  </button>
                  <button
                    onClick={handleSignOut}
                    className="focus-ring flex items-center gap-2 text-left font-body text-small text-navy/65 hover:text-gold transition-colors duration-fast py-2"
                  >
                    <LogOut size={13} aria-hidden="true" />
                    Sign Out
                  </button>
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </header>

    </>
  )
}

export default Header
