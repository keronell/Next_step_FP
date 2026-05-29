import { useState, useEffect } from 'react'
import { Menu, X, Sparkles } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import Button from './ui/Button.jsx'

function Header({ phase, onReset }) {
  const [menuOpen, setMenuOpen] = useState(false)
  const [scrolled, setScrolled] = useState(false)
  const [hovered, setHovered] = useState(null)

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24)
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  const scrollToSection = (id) => {
    setMenuOpen(false)
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  const navItems = [
    { label: 'Home', id: 'hero' },
    { label: 'How It Works', id: 'how-it-works' },
    { label: 'Assessment', id: 'assessment' },
    ...(phase === 'results_ready' ? [{ label: 'Results', id: 'results' }] : []),
  ]

  return (
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
          </motion.div>
        )}
      </AnimatePresence>
    </header>
  )
}

export default Header
