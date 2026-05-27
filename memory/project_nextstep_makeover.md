---
name: project-nextstep-makeover
description: Context for the Next Step career discovery app makeover — architecture, tech choices, and current state.
metadata:
  type: project
---

The Next Step frontend was completely remade into a single-page standalone React app.

**Why:** User wanted a visual makeover away from the dark theme, new Tailwind CSS setup, and a self-contained demo that doesn't require the backend to run.

**How to apply:** If making further frontend changes, this is now a standalone SPA. No React Router, no axios, no localStorage.

## Key Decisions
- **Single-page scroll layout** with phase state machine in App.jsx (idle → assessing → loading → results_ready)
- **Tailwind CSS** replaces all plain CSS files (old CSS files deleted)
- **Standalone** — all data hardcoded in `src/data.js`, no backend API calls
- **Fonts**: Playfair Display (headings) + Inter (body) via Google Fonts
- **Theme**: cream `#FAF7F2`, navy `#0F1B2D`, gold `#C9A84C`

## File Structure
- `src/App.jsx` — state machine, all phase/answer/career state
- `src/data.js` — QUESTIONS, CAREERS, WEIGHTS, computeResults(), ROADMAPS
- `src/hooks/useReveal.js` — IntersectionObserver scroll reveal hook
- `src/pages/Landing.jsx` → Hero section
- `src/pages/HowItWorks.jsx` → 3-step section (new file)
- `src/pages/Questionnaire.jsx` → Assessment section (3 phases: idle/assessing/loading)
- `src/pages/Results.jsx` → Career cards with count-up % animation
- `src/pages/Roadmap.jsx` → SVG tree with JS-driven path draw animation
- `tailwind.config.js` — custom cream/navy/gold color tokens

## SVG Path Animation Note
CSS class approach (stroke-dashoffset via CSS var) had unit mismatch issues.
Fixed by using direct JS: set `strokeDasharray=len; strokeDashoffset=len; transition=none`, then in a double-rAF set `transition=... ; strokeDashoffset=0`.
