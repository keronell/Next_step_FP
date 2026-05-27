import { useState, useEffect } from 'react'
import { Menu, X, Sparkles } from 'lucide-react'

function Header({ phase, onReset }) {
  const [menuOpen, setMenuOpen] = useState(false)
  const [scrolled, setScrolled] = useState(false)

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24)
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  const scrollToSection = (id) => {
    setMenuOpen(false)
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  return (
    <header
      className={`sticky top-0 z-50 transition-all duration-300 ${
        scrolled
          ? 'bg-cream/95 backdrop-blur-md shadow-sm border-b border-navy/8'
          : 'bg-transparent'
      }`}
    >
      <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
        {/* Logo */}
        <button
          onClick={onReset}
          className="flex flex-col items-start group"
        >
          <span className="font-display font-bold text-xl text-navy group-hover:text-navy/80 transition-colors leading-none">
            The Next Step
          </span>
          <span className="font-body text-[10px] font-medium text-gold tracking-widest uppercase leading-none mt-0.5">
            Career Discovery
          </span>
        </button>

        {/* Desktop nav */}
        <nav className="hidden md:flex items-center gap-8">
          {[
            { label: 'Home', id: 'hero' },
            { label: 'How It Works', id: 'how-it-works' },
            { label: 'Assessment', id: 'assessment' },
            ...(phase === 'results_ready' ? [{ label: 'Results', id: 'results' }] : []),
          ].map((item) => (
            <button
              key={item.id}
              onClick={() => scrollToSection(item.id)}
              className="font-body text-sm text-navy/70 hover:text-navy transition-colors relative group"
            >
              {item.label}
              <span className="absolute -bottom-0.5 left-0 right-0 h-px bg-gold scale-x-0 group-hover:scale-x-100 transition-transform duration-200 origin-left" />
            </button>
          ))}
          <button
            onClick={() => scrollToSection('assessment')}
            className="btn-gold px-5 py-2 rounded-full text-sm font-semibold font-body flex items-center gap-1.5"
          >
            <Sparkles size={14} />
            Start Assessment
          </button>
        </nav>

        {/* Mobile hamburger */}
        <button
          className="md:hidden p-2 text-navy hover:text-navy/70 transition-colors"
          onClick={() => setMenuOpen(!menuOpen)}
          aria-label="Toggle menu"
        >
          {menuOpen ? <X size={22} /> : <Menu size={22} />}
        </button>
      </div>

      {/* Mobile dropdown */}
      {menuOpen && (
        <div className="md:hidden bg-cream/98 backdrop-blur-md border-b border-navy/10 px-6 py-4 flex flex-col gap-3">
          {['hero', 'how-it-works', 'assessment'].map((id) => (
            <button
              key={id}
              onClick={() => scrollToSection(id)}
              className="text-left font-body text-navy/80 hover:text-navy py-2 border-b border-navy/5 last:border-0 transition-colors capitalize"
            >
              {id.replace('-', ' ')}
            </button>
          ))}
          <button
            onClick={() => scrollToSection('assessment')}
            className="btn-gold px-5 py-2.5 rounded-full text-sm font-semibold font-body mt-1"
          >
            Start Assessment
          </button>
        </div>
      )}
    </header>
  )
}

export default Header
