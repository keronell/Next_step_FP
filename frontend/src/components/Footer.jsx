import { ArrowUp, Sparkles, Github, Twitter, Linkedin } from 'lucide-react'
import { motion } from 'framer-motion'

const NAV_LINKS = [
  { label: 'Home', id: 'hero' },
  { label: 'How It Works', id: 'how-it-works' },
  { label: 'Assessment', id: 'assessment' },
]

const RESOURCE_LINKS = [
  { label: 'Career Matches', id: 'results' },
  { label: 'Learning Roadmap', id: 'roadmap' },
]

const SOCIALS = [
  { icon: Github, label: 'GitHub', href: '#' },
  { icon: Twitter, label: 'Twitter', href: '#' },
  { icon: Linkedin, label: 'LinkedIn', href: '#' },
]

function scrollToId(id) {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function FooterColumn({ title, links }) {
  return (
    <div className="flex flex-col gap-4">
      <p className="font-body text-eyebrow font-semibold uppercase text-gold">{title}</p>
      <ul className="flex flex-col gap-3">
        {links.map((item) => (
          <li key={item.id}>
            <button
              onClick={() => scrollToId(item.id)}
              className="focus-ring group inline-flex items-center gap-2 text-small font-body text-cream/75 hover:text-cream transition-colors duration-fast rounded-sm"
            >
              <span className="h-px w-0 bg-gold transition-all duration-base group-hover:w-4" />
              {item.label}
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}

function Footer({ onReset }) {
  const scrollTop = () => window.scrollTo({ top: 0, behavior: 'smooth' })

  return (
    <footer className="relative mt-24 overflow-hidden bg-navy text-cream">
      {/* Gold glow blobs */}
      <div aria-hidden="true" className="pointer-events-none absolute inset-0">
        <div className="absolute -top-24 left-1/4 h-72 w-72 rounded-full bg-gold/20 blur-3xl animate-glow" />
        <div className="absolute bottom-0 right-1/4 h-80 w-80 rounded-full bg-gold-light/10 blur-3xl animate-glow [animation-delay:2s]" />
      </div>
      {/* Top hairline */}
      <div aria-hidden="true" className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-gold/50 to-transparent" />

      <motion.div
        initial={{ opacity: 0, y: 30 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, amount: 0.3 }}
        transition={{ duration: 0.6, ease: [0.25, 0.46, 0.45, 0.94] }}
        className="relative z-10 max-w-6xl mx-auto px-6 py-16"
      >
        <div className="grid grid-cols-1 gap-12 md:grid-cols-12">
          {/* Brand */}
          <div className="md:col-span-5 flex flex-col gap-5">
            <button
              onClick={onReset}
              className="focus-ring flex items-center gap-2 group rounded-md w-fit"
            >
              <span className="grid place-items-center h-9 w-9 rounded-full bg-gold/15 ring-1 ring-gold/30">
                <Sparkles size={18} className="text-gold" aria-hidden="true" />
              </span>
              <span className="font-display font-bold text-xl text-cream group-hover:text-gold transition-colors duration-fast">
                The Next Step
              </span>
            </button>
            <p className="font-body text-small text-cream/70 max-w-sm leading-relaxed">
              Discover your ideal tech career with a personalized assessment and a clear,
              step-by-step learning roadmap to get there.
            </p>
            <div className="flex items-center gap-3">
              {SOCIALS.map(({ icon: Icon, label, href }) => (
                <a
                  key={label}
                  href={href}
                  aria-label={label}
                  className="focus-ring grid place-items-center h-10 w-10 rounded-full border border-cream/15 text-cream/70 hover:text-gold hover:border-gold/60 hover:-translate-y-0.5 transition-all duration-fast"
                >
                  <Icon size={17} aria-hidden="true" />
                </a>
              ))}
            </div>
          </div>

          {/* Link columns */}
          <div className="md:col-span-4 grid grid-cols-2 gap-8">
            <FooterColumn title="Explore" links={NAV_LINKS} />
            <FooterColumn title="Your Results" links={RESOURCE_LINKS} />
          </div>

          {/* Back to top */}
          <div className="md:col-span-3 flex md:justify-end md:items-start">
            <button
              onClick={scrollTop}
              className="focus-ring group inline-flex items-center gap-2 px-5 py-2.5 rounded-full border border-cream/20 text-cream/85 hover:border-gold hover:text-gold transition-all duration-fast text-small font-body font-medium"
            >
              <ArrowUp
                size={15}
                className="group-hover:-translate-y-0.5 transition-transform duration-fast"
                aria-hidden="true"
              />
              Back to top
            </button>
          </div>
        </div>

        {/* Bottom bar */}
        <div className="mt-14 pt-6 border-t border-cream/10 flex flex-col md:flex-row items-center justify-between gap-3">
          <p className="font-body text-eyebrow uppercase tracking-wider text-cream/55">
            © 2026 The Next Step · Career Discovery Platform
          </p>
          <p className="font-body text-eyebrow uppercase tracking-wider text-cream/55">
            All data stays in your browser · No account required
          </p>
        </div>
      </motion.div>
    </footer>
  )
}

export default Footer
