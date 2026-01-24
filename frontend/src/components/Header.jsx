import { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import './Header.css'

function Header() {
  const [isMenuOpen, setIsMenuOpen] = useState(false)
  const location = useLocation()

  const isActive = (path) => {
    return location.pathname === path
  }

  const toggleMenu = () => {
    setIsMenuOpen(!isMenuOpen)
  }

  return (
    <header className="header">
      <div className="header-container">
        <Link to="/" className="header-logo">
          <span className="logo-text">NextStep</span>
          <span className="logo-subtitle">Career Matcher</span>
        </Link>

        <nav className={`header-nav ${isMenuOpen ? 'nav-open' : ''}`}>
          <Link 
            to="/" 
            className={`nav-link ${isActive('/') ? 'active' : ''}`}
            onClick={() => setIsMenuOpen(false)}
          >
            Home
          </Link>
          <Link 
            to="/questionnaire" 
            className={`nav-link ${isActive('/questionnaire') ? 'active' : ''}`}
            onClick={() => setIsMenuOpen(false)}
          >
            Assessment
          </Link>
          <Link 
            to="/results" 
            className={`nav-link ${isActive('/results') ? 'active' : ''}`}
            onClick={() => setIsMenuOpen(false)}
          >
            Results
          </Link>
          <Link 
            to="/roadmap" 
            className={`nav-link ${isActive('/roadmap') ? 'active' : ''}`}
            onClick={() => setIsMenuOpen(false)}
          >
            Roadmap
          </Link>
        </nav>

        <button 
          className="header-menu-toggle"
          onClick={toggleMenu}
          aria-label="Toggle menu"
        >
          <span className={`menu-icon ${isMenuOpen ? 'open' : ''}`}>
            <span></span>
            <span></span>
            <span></span>
          </span>
        </button>
      </div>
    </header>
  )
}

export default Header
