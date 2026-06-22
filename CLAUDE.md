# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Most important thing to know

**The live app is a standalone frontend SPA. It does not talk to the backend.**

`README.md`, `SETUP.md`, and `start.js` describe an older architecture (Flask + SQLite + a react-router frontend hitting `/api`). That is stale. The current frontend (`frontend/src/App.jsx`) is a single-page app driven by a phase state machine, with all questions, career data, matching, and roadmaps living client-side in `frontend/src/data.js`. There are no API calls in the running app, no react-router, and `axios` is not even a dependency.

Implications:
- To change questions, careers, the matching logic, or roadmaps, edit `frontend/src/data.js` — **not** the backend.
- The Vite proxy to `localhost:3001` (`frontend/vite.config.js`) and the Flask backend in `backend/` are vestigial for the live app. Don't wire new frontend features through them unless you're deliberately reviving the backend.
- `frontend/src/pages/AdaptiveQuestionnaire.jsx` is orphaned (imports `axios`, calls `/api`, not imported by `App.jsx`). It would break the build if imported. Ignore it unless reviving the backend flow.

## Commands

Everything runs from `frontend/`:

```bash
cd frontend
npm install
npm run dev      # dev server on http://localhost:3000
npm run build    # production build -> frontend/dist (use this to verify changes)
npm run preview  # serve the production build
```

There is no lint or test setup in this repo (no eslint config, no test runner). Verify changes with `npm run build`.

Ignore the root `npm start` / `./start.sh` / `start.js` and the backend setup steps in `SETUP.md` unless you specifically need the (unused) Flask backend.

## Frontend architecture

Single page, scroll-based, sections stacked in `App.jsx`. A `phase` string in `App.jsx` is the source of truth and gates what each section renders:

```
idle → assessing → loading → results_ready
```

- `handleStart` → `assessing` (scrolls to the Assessment section)
- `handleQuizComplete(answers)` → `loading`, then after a ~2.6s timeout calls `computeResults(answers)` from `data.js`, stores top matches, → `results_ready`
- `handleSelectCareer` sets `selectedCareer` and scrolls to the Roadmap section
- `handleReset` → back to `idle`

Sections (`frontend/src/pages/`): `Landing.jsx` (Hero), `HowItWorks.jsx`, `Questionnaire.jsx` (exported as `Assessment`), `Results.jsx`, `Roadmap.jsx`. Each receives `phase` and renders null / a sub-view based on it (e.g. `Questionnaire` internally switches between `answering`, `review`, and `loading` screens).

`data.js` exports: `QUESTIONS`, `CAREERS`, `computeResults(answers)` (the client-side matcher returning top matches), and `ROADMAPS` (keyed by career id).

## Styling

Tailwind (`frontend/tailwind.config.js`) with a custom theme: `cream` / `navy` / `gold` color tokens (backed by CSS variables in `frontend/src/index.css`), plus custom `font-display` / `font-body`, radius (`rounded-card`), and duration (`duration-base` / `duration-fast`) tokens. Animations use `framer-motion`; icons come from `lucide-react`. Reuse these tokens rather than hardcoding values.

## Backend and data pipeline (separate from the live app)

- `backend/` — Flask + SQLite REST API (sessions, questions, matching, roadmaps). Documented in `README.md`. Not consumed by the current frontend.
- `data/` (repo root) — a separate data-engineering pipeline (scripts, jobs, models, questions, reports, visualizations) with its own `README.md`. Not part of the running app.

## Branches

Active branches: `main`, `Ronen`, `vlad`. The current SPA frontend came from the `Ronen` redesign; `vlad` contributed the adaptive quiz and data pipeline. When merging frontend work, keep `main` and `Ronen` in sync.
