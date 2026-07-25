import { useEffect, useRef, useState } from 'react'
import { ChevronDown, Clock, LogOut, Map, Menu, Shield, Sparkles, X } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import Button from './ui/Button.jsx'
import History from '../pages/History'
import { useAuth } from '../contexts/AuthContext'
import { navigate, navigateToSection, requestHistoryOpen, consumePendingHistoryOpen } from '../hooks/useRoute'

// `roadmapCareerId` is the career whose roadmap a returning user can jump straight
// to (their most recent completed assessment). When set, we surface a "My Roadmap"
// shortcut that deep-links past the intro/questionnaire (DEV-76). It's null for
// users with no completed assessment, so the shortcut simply never appears.
//
// `onHistoryLoadResults` is passed ONLY by RoadmapPage — it's how "Past
// assessments" living there (rather than on the homepage) reaches the account
// menu's "My History" item: when present, that item expands the list in place;
// everywhere else it has nowhere to expand into, so it falls back to routing to
// the roadmap page (same as "My Roadmap").
function Header({ phase, onReset, onOpenAuth, onStartAssessment, roadmapCareerId, onHistoryLoadResults }) {
  const { user, authLoading, signOut } = useAuth()

  const [menuOpen, setMenuOpen] = useState(false)
  const [scrolled, setScrolled] = useState(false)
  const [hovered, setHovered] = useState(null)
  const [accountOpen, setAccountOpen] = useState(false)
  const [historyOpen, setHistoryOpen] = useState(false)
  const accountRef = useRef(null)
  const mobileMenuRef = useRef(null)

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24)
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  // Arriving on the roadmap page via a "My History" click made elsewhere (see
  // toggleHistory's else branch below): open the account menu with history
  // already expanded, so the click actually shows history instead of silently
  // landing on the roadmap like "My Roadmap" would. Only ever true on the mount
  // right after that click — consumePendingHistoryOpen() clears it either way.
  // Both accountOpen (desktop dropdown) and menuOpen (mobile panel) are set
  // since only one of the two is visible per breakpoint (md:flex / md:hidden) —
  // setting just accountOpen left mobile taps looking like they did nothing,
  // because the mobile history section only renders inside {menuOpen && ...}.
  useEffect(() => {
    if (onHistoryLoadResults && consumePendingHistoryOpen()) {
      setAccountOpen(true)
      setMenuOpen(true)
      setHistoryOpen(true)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Close account dropdown (and the history panel nested in it) on outside click.
  // Checks BOTH containers: the deferred-open effect above can set accountOpen
  // true while the visible panel is actually the mobile one (mobileMenuRef), and
  // accountRef alone wouldn't contain clicks there — a tap on a history card's
  // Load/Delete button would fire this handler's 'mousedown' first, read as
  // "outside", and unmount the panel before the button's own 'click' handler runs.
  useEffect(() => {
    if (!accountOpen) return
    const handler = (e) => {
      const insideDesktop = accountRef.current?.contains(e.target)
      const insideMobile = mobileMenuRef.current?.contains(e.target)
      if (!insideDesktop && !insideMobile) {
        setAccountOpen(false)
        setHistoryOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [accountOpen])

  const scrollToSection = (id) => {
    setMenuOpen(false)
    setAccountOpen(false)
    setHistoryOpen(false)
    // Scrolls now if the section is on this page; otherwise routes home and defers
    // the scroll until it mounts, so the link still lands on its target section
    // (rather than the top of the homepage) from the standalone roadmap route.
    navigateToSection(id)
  }

  // Leaving mid-assessment unmounts Questionnaire/Profile, whose quiz answers and
  // unsaved form edits are component-local — the roadmap route is an exclusive
  // branch in App, so returning would restart the quiz or drop the profile draft.
  // The shortcut only exists for RETURNING users, so hiding it here costs nothing.
  const midAssessment = phase === 'assessing' || phase === 'profiling'
  const showRoadmapShortcut = roadmapCareerId && !midAssessment
  // DEV-62: the admin screen replaces the scroll app, so like the roadmap shortcut
  // it stays hidden mid-run rather than unmounting a half-finished assessment.
  const showAdminLink = user?.role === 'admin' && !midAssessment

  const goToAdmin = () => {
    setAccountOpen(false)
    setMenuOpen(false)
    navigate('/admin')
  }

  const goToRoadmap = () => {
    setMenuOpen(false)
    setAccountOpen(false)
    setHistoryOpen(false)
    navigate(`/roadmap/${encodeURIComponent(roadmapCareerId)}`)
  }

  // "My History": on the roadmap page (onHistoryLoadResults provided) it expands
  // the list in place; everywhere else it routes to the roadmap page instead,
  // since that's the only place the list is rendered — flagging the intent first
  // so the roadmap page's own Header opens it back up on arrival (see the mount
  // effect above), rather than leaving the user to find "My History" again.
  const toggleHistory = () => {
    if (onHistoryLoadResults) {
      setHistoryOpen((v) => !v)
    } else {
      requestHistoryOpen()
      goToRoadmap()
    }
  }

  // The Assessment nav item and Start Assessment buttons go through the parent so
  // it can reset the flow first — the assessment section renders nothing while the
  // (possibly background-restored) phase is 'results_ready', so a plain scroll would
  // land the user on a blank section.
  const startAssessment = () => {
    setMenuOpen(false)
    setAccountOpen(false)
    setHistoryOpen(false)
    onStartAssessment()
  }

  const handleSignOut = async () => {
    setAccountOpen(false)
    setMenuOpen(false)
    setHistoryOpen(false)
    await signOut()
  }

  const navItems = [
    { label: 'Home', id: 'hero' },
    { label: 'How It Works', id: 'how-it-works' },
    { label: 'Assessment', id: 'assessment' },
    ...(phase === 'results_ready' ? [{ label: 'Results', id: 'results' }] : []),
  ]

  const displayUsername = user?.username || user?.email || ''

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
                  onClick={() => (item.id === 'assessment' ? startAssessment() : scrollToSection(item.id))}
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
                  onMouseEnter={() => setHovered('__signin')}
                  className="focus-ring relative px-4 py-2 rounded-full font-body text-small text-navy/75 hover:text-navy transition-colors duration-fast"
                >
                  {hovered === '__signin' && (
                    <motion.span
                      layoutId="nav-pill"
                      className="absolute inset-0 rounded-full bg-gold/12 ring-1 ring-inset ring-gold/25"
                      transition={{ type: 'spring', stiffness: 380, damping: 30 }}
                    />
                  )}
                  <span className="relative z-10">Sign In</span>
                </button>
              )}

              {!authLoading && user && (
                <div ref={accountRef} className="relative ml-1">
                  <button
                    onClick={() => setAccountOpen((v) => !v)}
                    onMouseEnter={() => setHovered('__account')}
                    className="focus-ring relative flex items-center gap-1.5 px-4 py-2 rounded-full font-body text-small text-navy/75 hover:text-navy transition-colors duration-fast"
                  >
                    {hovered === '__account' && (
                      <motion.span
                        layoutId="nav-pill"
                        className="absolute inset-0 rounded-full bg-gold/12 ring-1 ring-inset ring-gold/25"
                        transition={{ type: 'spring', stiffness: 380, damping: 30 }}
                      />
                    )}
                    <span className="relative z-10 max-w-[120px] truncate">{displayUsername}</span>
                    <motion.span
                      className="relative z-10"
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
                        className={`absolute right-0 top-full mt-2 bg-white rounded-2xl border border-navy/[0.08] shadow-lg py-2 z-10 transition-[width] duration-200 ${
                          historyOpen && onHistoryLoadResults ? 'w-[26rem]' : 'w-52'
                        }`}
                      >
                        <div className="px-4 py-2 border-b border-navy/[0.06]">
                          <p className="font-body text-eyebrow text-navy/40 uppercase font-semibold">Signed in as</p>
                          <p className="font-body text-small text-navy font-medium truncate mt-0.5">{user.username || user.email}</p>
                        </div>
                        {showRoadmapShortcut && (
                          <button
                            onClick={goToRoadmap}
                            className="focus-ring w-full text-left flex items-center gap-2.5 px-4 py-2.5 font-body text-small text-navy/70 hover:text-navy hover:bg-navy/[0.04] transition-colors duration-fast"
                          >
                            <Map size={14} aria-hidden="true" className="text-navy/40" />
                            My Roadmap
                          </button>
                        )}
                        {/* Past assessments now live on the roadmap page (moved off the
                            homepage). Here (on the roadmap page itself) this expands the
                            list in place; elsewhere it routes there via toggleHistory. */}
                        {(showRoadmapShortcut || onHistoryLoadResults) && (
                          <button
                            onClick={toggleHistory}
                            className="focus-ring w-full text-left flex items-center gap-2.5 px-4 py-2.5 font-body text-small text-navy/70 hover:text-navy hover:bg-navy/[0.04] transition-colors duration-fast"
                          >
                            <Clock size={14} aria-hidden="true" className="text-navy/40" />
                            My History
                            {onHistoryLoadResults && (
                              <motion.span
                                className="ml-auto"
                                animate={{ rotate: historyOpen ? 180 : 0 }}
                                transition={{ duration: 0.2 }}
                              >
                                <ChevronDown size={13} aria-hidden="true" className="text-navy/40" />
                              </motion.span>
                            )}
                          </button>
                        )}
                        {onHistoryLoadResults && historyOpen && (
                          <div className="max-h-96 overflow-y-auto border-t border-navy/[0.06]">
                            <History
                              user={user}
                              onLoadResults={(...args) => {
                                setAccountOpen(false)
                                setMenuOpen(false)
                                setHistoryOpen(false)
                                onHistoryLoadResults(...args)
                              }}
                            />
                          </div>
                        )}
                        {showAdminLink && (
                          <button
                            onClick={goToAdmin}
                            className="focus-ring w-full text-left flex items-center gap-2.5 px-4 py-2.5 font-body text-small text-navy/70 hover:text-navy hover:bg-navy/[0.04] transition-colors duration-fast"
                          >
                            <Shield size={14} aria-hidden="true" className="text-navy/40" />
                            Admin
                          </button>
                        )}
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
                onClick={startAssessment}
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

        {/* Mobile dropdown. mobileMenuRef sits on this always-present wrapper rather
            than on AnimatePresence's own animated child — motion.div there clashes
            with AnimatePresence's internal ref handling (dev warning: "ref is not
            a prop"). Keeping the ref off that child is what makes it reliably
            available for the outside-click containment check above. */}
        <div ref={mobileMenuRef}>
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
                  onClick={() => (item.id === 'assessment' ? startAssessment() : scrollToSection(item.id))}
                  className="focus-ring text-left font-body text-navy/80 hover:text-gold py-2.5 border-b border-navy/5 last:border-0 transition-colors duration-fast"
                >
                  {item.label}
                </button>
              ))}

              <Button
                variant="primary"
                size="md"
                onClick={startAssessment}
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
                    {user.username || user.email}
                  </p>
                  {showRoadmapShortcut && (
                    <button
                      onClick={goToRoadmap}
                      className="focus-ring flex items-center gap-2 text-left font-body text-small text-navy/65 hover:text-gold transition-colors duration-fast py-2"
                    >
                      <Map size={13} aria-hidden="true" />
                      My Roadmap
                    </button>
                  )}
                  {(showRoadmapShortcut || onHistoryLoadResults) && (
                    <button
                      onClick={toggleHistory}
                      className="focus-ring flex items-center gap-2 text-left font-body text-small text-navy/65 hover:text-gold transition-colors duration-fast py-2"
                    >
                      <Clock size={13} aria-hidden="true" />
                      My History
                      {onHistoryLoadResults && (
                        <motion.span
                          className="ml-auto"
                          animate={{ rotate: historyOpen ? 180 : 0 }}
                          transition={{ duration: 0.2 }}
                        >
                          <ChevronDown size={12} aria-hidden="true" />
                        </motion.span>
                      )}
                    </button>
                  )}
                  {onHistoryLoadResults && historyOpen && (
                    <div className="max-h-80 overflow-y-auto">
                      <History
                        user={user}
                        onLoadResults={(...args) => {
                          setMenuOpen(false)
                          setAccountOpen(false)
                          setHistoryOpen(false)
                          onHistoryLoadResults(...args)
                        }}
                      />
                    </div>
                  )}
                  {showAdminLink && (
                    <button
                      onClick={goToAdmin}
                      className="focus-ring flex items-center gap-2 text-left font-body text-small text-navy/65 hover:text-gold transition-colors duration-fast py-2"
                    >
                      <Shield size={13} aria-hidden="true" />
                      Admin
                    </button>
                  )}
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
        </div>
      </header>

    </>
  )
}

export default Header
