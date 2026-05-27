import { ArrowUp, Sparkles } from 'lucide-react'

function Footer({ onReset }) {
  const scrollTop = () => window.scrollTo({ top: 0, behavior: 'smooth' })

  return (
    <footer className="bg-navy text-cream/70 mt-24">
      <div className="max-w-6xl mx-auto px-6 py-16">
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-8">
          {/* Brand */}
          <div className="flex flex-col gap-2">
            <button onClick={onReset} className="flex items-center gap-2 group">
              <Sparkles size={18} className="text-gold" />
              <span className="font-display font-bold text-xl text-cream group-hover:text-cream/80 transition-colors">
                The Next Step
              </span>
            </button>
            <p className="font-body text-sm text-cream/50 max-w-sm leading-relaxed">
              Discover your ideal tech career with a personalized assessment and a clear learning roadmap.
            </p>
          </div>

          {/* Links */}
          <div className="flex flex-col gap-3 text-sm font-body">
            {[
              { label: 'Home', id: 'hero' },
              { label: 'How It Works', id: 'how-it-works' },
              { label: 'Assessment', id: 'assessment' },
            ].map((item) => (
              <button
                key={item.id}
                onClick={() => document.getElementById(item.id)?.scrollIntoView({ behavior: 'smooth' })}
                className="text-left text-cream/50 hover:text-gold transition-colors"
              >
                {item.label}
              </button>
            ))}
          </div>

          {/* Back to top */}
          <button
            onClick={scrollTop}
            className="flex items-center gap-2 px-5 py-2.5 rounded-full border border-cream/20 hover:border-gold hover:text-gold transition-all text-sm font-body font-medium group"
          >
            <ArrowUp size={15} className="group-hover:-translate-y-0.5 transition-transform" />
            Back to top
          </button>
        </div>

        <div className="mt-12 pt-6 border-t border-cream/10 flex flex-col md:flex-row items-center justify-between gap-3">
          <p className="font-body text-xs text-cream/30">
            © 2026 The Next Step · Career Discovery Platform
          </p>
          <p className="font-body text-xs text-cream/30">
            All data stays in your browser · No account required
          </p>
        </div>
      </div>
    </footer>
  )
}

export default Footer
