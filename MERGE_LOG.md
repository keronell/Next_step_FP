# Merge Log

> **Update (2026-06-24):** Some files recorded below were removed after these merges,
> when the backend moved to the FastAPI RAG architecture: `backend/app.py`,
> `backend/db/`, `backend/scripts/seed.py`, `frontend/src/pages/AdaptiveQuestionnaire.jsx`,
> and the `start.js`/`start.sh`/`start.bat` launchers. The entries below are kept
> verbatim as the historical record of what each merge contained at the time.

---

## Merge 2: Ronen → main

**Date:** 2026-06-13  
**Merged by:** keronell  
**Base commit (old main):** `efc8ab9`  
**Merge commit (new main):** `19d6c0f`  
**Branch merged:** `Ronen`  
**Files changed:** 47 files — 5,040 insertions, 3,958 deletions

### Commits merged (oldest → newest)

| Hash | Message |
|------|---------|
| `2f32011` | Add modal functionality to Landing page; implement modal styles and animations; update Questionnaire with sidebar navigation and answer review |
| `a4117e9` | Refactor Landing page CSS for improved layout and aesthetics |
| `c8f5f2c` | Refactor Questionnaire CSS for improved consistency and aesthetics |
| `e8ad203` | Enhance Questionnaire CSS for visual hierarchy; add styles for sidebar question items |
| `3030c0a` | Remove obsolete binary document file |
| `b2f7101` | Refactor App component and enhance styling; replace deprecated CSS with Tailwind CSS; integrate new UI components; update dependencies |
| `4c02200` | Refactor Roadmap structure to use sections; update node properties to include type and resources |
| `3bd0474` | Adjust step number badge position in HowItWorks cards |
| `b149b30` | Implement particle animation on Landing page; add CSS for visual effects; improve Questionnaire and Results loading; refactor Roadmap node reveal logic |
| `04a816a` | Remove obsolete image files |
| `e9507fa` | Remove server-info file |
| `fe67060` | Remove multiple obsolete YAML files |
| `ba7dd77` | Refactor particle animation logic; improve canvas resizing with ResizeObserver |
| `7d9cf52` | windows starter |
| `19d6c0f` | **Merge commit** — Merge branch Ronen: frontend redesign with Tailwind CSS and single-page architecture |

### Conflict resolution

4 content conflicts and 2 modify/delete conflicts were resolved in favour of Ronen's version:

| File | Conflict type | Resolution |
|------|--------------|------------|
| `frontend/src/App.jsx` | Content | Took Ronen's (single-page scroll, no router) |
| `frontend/src/pages/Landing.jsx` | Content | Took Ronen's (particle animation, Tailwind) |
| `frontend/src/pages/Results.jsx` | Content | Took Ronen's (match % display, static data) |
| `frontend/src/pages/Roadmap.jsx` | Content | Took Ronen's (section-based, node resources) |
| `frontend/src/pages/Landing.css` | Modify/delete | Deleted (Ronen removed in favour of Tailwind) |
| `frontend/src/pages/Questionnaire.css` | Modify/delete | Deleted (Ronen removed in favour of Tailwind) |

**Architectural note:** Ronen's branch replaced the React Router multi-page app (vlad) with a single-page scroll architecture. Backend API calls and session management were removed from the frontend; results are now computed locally from `data.js`.

### Changes by area

**Frontend — architecture (`frontend/src/`)**
- `App.jsx` — rewritten: removed React Router, ToastProvider, sessionId state; now manages phase/results/selectedCareer state with scroll-based section navigation
- `index.css` — expanded with Tailwind base + custom design tokens
- `App.css` — deleted (replaced by Tailwind)

**Frontend — new UI components (`frontend/src/components/ui/`)**
- `Button.jsx` — reusable button with variant support
- `Badge.jsx` — label badge component
- `Card.jsx` — card container
- `Eyebrow.jsx` — section eyebrow label
- `SectionHeading.jsx` — styled section header

**Frontend — removed components**
- `Toast.jsx` + `Toast.css`, `ToastContainer.jsx` + `ToastContainer.css` — removed (no longer needed)
- `LoadingSkeleton.jsx` + `LoadingSkeleton.css` — removed
- `Footer.css`, `Header.css` — removed (replaced by Tailwind)

**Frontend — pages**
- `Landing.jsx` — rewritten: particle canvas animation with ResizeObserver, framer-motion hero, single CTA button
- `Questionnaire.jsx` — rewritten: sidebar navigation with answer review, improved loading states
- `Results.jsx` — rewritten: match percentage display, career card layout using static computed results
- `Roadmap.jsx` — rewritten: section-based node structure with resources per node, reveal animation
- `HowItWorks.jsx` — new page/section added
- `Progress.jsx`, `NotFound.jsx`, `AdaptiveQuestionnaire.jsx` — deleted (routing removed)

**Frontend — removed CSS files**
- `Landing.css`, `Questionnaire.css`, `Results.css`, `Roadmap.css`, `Progress.css`, `NotFound.css`

**Frontend — new files**
- `data.js` — static question bank + `computeResults()` scoring logic (701 lines)
- `hooks/useReveal.js` — IntersectionObserver hook for scroll-triggered reveals
- `lib/utils.js` — utility helpers (clsx/twMerge)
- `tailwind.config.js` — Tailwind configuration with custom colors and fonts
- `postcss.config.js` — PostCSS config for Tailwind

**Frontend — dependencies**
- `package.json` — added: `tailwindcss`, `framer-motion`, `lucide-react`, `clsx`, `tailwind-merge`; removed: `react-router-dom`, `axios`

**Root level**
- `start.bat` — Windows startup script added
- Obsolete YAML files, binary `.docx` file, image assets removed

---

## Merge 1: vlad → main

**Date:** 2026-06-13  
**Merged by:** keronell  
**Base commit (old main):** `62ce969`  
**Merge commit (new main):** `efc8ab9`  
**Branch merged:** `vlad`  
**Files changed:** 97 files — 212,997 insertions, 140 deletions

---

## Commits merged (oldest → newest)

| Hash | Message |
|------|---------|
| `e145401` | modificate data and add branch |
| `55ab1f7` | Merge remote-tracking branch 'origin/main' into vlad |
| `4cbf80a` | Merge remote-tracking branch 'origin/main' into vlad |
| `35cda9f` | Add adaptive quiz functionality with new API endpoints for starting sessions and submitting answers; implement expert answer loading and job scoring logic; update database schema to support adaptive mode and answer types; enhance requirements with numpy and openai dependencies |
| `427c3be` | expert answers logic + local model logic + adaptive quiz logic |
| `b47cabf` | Implement question validation and error handling in adaptive quiz submission; add function to ensure questions exist in the database, enhancing data integrity. Update frontend error handling for improved user feedback during answer submission |
| `4add921` | Enhance job scoring and results processing in adaptive quiz; add validation checks for user answers and remaining jobs, improve debug logging for better traceability, and ensure fallback mechanisms for score computation. Update frontend to handle adaptive results more robustly with detailed logging and score handling |
| `9329e03` | fix bugs with roadmap session ID |
| `5be0706` | Add presentation notes and structure for the NextStep Career Matcher project |
| `d9f8f3f` | Update subproject commit to indicate a dirty state, reflecting uncommitted changes in the data directory |
| `86f35dd` | Update data submodule reference |
| `73f6c33` | label antology fix |
| `1a62cbf` | Replace data submodule with tracked files |
| `bbf85ce` | Update requirements and restructure data files |
| `fd37511` | Merge origin/vlad: resolve requirements.txt conflict |
| `1fb23d7` | Update requirements.txt to include pandas, requests, and tqdm for annotation scripts; resolve conflicts and clean up duplicate question bank CSVs |
| `28a2f0d` | Refactor data/ directory: consolidate scripts, add README files, untrack generated files |
| `efc8ab9` | **Merge commit** — Merge branch vlad: adaptive quiz, data pipeline, frontend improvements |

---

## Changes by area

### Backend (`backend/`)

**Modified:**
- `backend/app.py` — +883/-169 lines: adaptive quiz endpoints, job scoring logic, roadmap session ID fix, improved error handling and validation

**Schema:**
- `backend/db/schema.py` — added adaptive mode and answer type columns

**New config files:**
- `backend/config/adaptive_quiz_config.json` — adaptive quiz parameters
- `backend/config/label_ontology.json` — 40-label ontology for question classification
- `backend/config/label_to_skill_mapping.json` — maps abstract labels to concrete skills

**New data files:**
- `backend/data/expert_answers.json` — full synthetic expert answer dataset (112,772 lines)
- `backend/data/expert_answers_by_job.json` — answers indexed by job/field (16,132 lines)
- `backend/data/expert_answers_by_question.json` — answers indexed by question (19,334 lines)
- `backend/data/top_10_jobs.json` — top job listings per field

**New scripts:**
- `backend/scripts/generate_expert_answers.py` — generates expert answers via LLM
- `backend/scripts/generate_expert_answers_free.py` — uses free LLM providers
- `backend/scripts/create_expert_database.py` — builds the expert answer DB
- `backend/scripts/select_top_jobs.py` — selects representative jobs per field
- `backend/scripts/test_ollama.py` — tests local Ollama connection

**New documentation:**
- `backend/scripts/README_ADAPTIVE_QUIZ.md` — full adaptive quiz system docs
- `backend/scripts/QUICK_START_OLLAMA.md` — Ollama setup guide
- `backend/scripts/SETUP_FREE_PROVIDERS.md` — free LLM provider setup
- `backend/scripts/TODO_EXPERT_ANSWERS.md` — outstanding tasks

**Dependencies:**
- `backend/requirements.txt` — added numpy, openai

---

### Frontend (`frontend/`)

**Modified:**
- `frontend/src/App.jsx` — added AdaptiveQuestionnaire route, NotFound route
- `frontend/src/pages/Landing.jsx` — +35/-1: Toast integration, UI updates
- `frontend/src/pages/Results.jsx` — +130 lines: adaptive results handling, field score display
- `frontend/src/pages/Roadmap.jsx` — +20 lines: session ID fix, improved loading
- `frontend/src/pages/Questionnaire.jsx` — improved error handling
- `frontend/src/pages/Progress.jsx` — Toast integration

**New pages:**
- `frontend/src/pages/AdaptiveQuestionnaire.jsx` — full adaptive quiz UI (230 lines)
- `frontend/src/pages/NotFound.jsx` + `NotFound.css` — 404 page

**New components:**
- `frontend/src/components/Toast.jsx` + `Toast.css` — toast notification component
- `frontend/src/components/ToastContainer.jsx` + `ToastContainer.css` — toast stack manager
- `frontend/src/components/LoadingSkeleton.jsx` + `LoadingSkeleton.css` — skeleton loading states

**New CSS:**
- `frontend/src/pages/Landing.css`
- `frontend/src/pages/Questionnaire.css`
- `frontend/src/pages/Results.css`
- `frontend/src/pages/Roadmap.css`

---

### Data pipeline (`data/`)

**New directory structure** (previously a git submodule, now fully tracked files):

| Directory | Contents |
|-----------|----------|
| `data/questions/` | `question_bank.csv` (1,611 questions), `question_bank_labeled.csv` (auto-labeled) |
| `data/answers/` | `question_bank_answered_local.csv` (5,760 synthetic answers), `annotation_failures.jsonl` |
| `data/config/` | `field_taxonomy.json`, `label_ontology.json`, `label_schema.json`, `label_schema_examples.jsonl`, `skill_aliases.json` |
| `data/jobs/raw/` | Scraped job JSONs: arbeitnow, jobicy, jobspy, remoteok, remotive, themuse, weworkremotely, workingnomads |
| `data/visualizations/` | 5 label distribution charts (PNG) |
| `data/reports/` | Quality audit reports, trust-check results, validation summaries |
| `data/docs/` | Design docs: adaptive questionnaire spec, labeling summary, neural matcher design |
| `data/models/` | Placeholder for trained model artifacts |

**New scripts** (all in `data/scripts/`):
- `scrape_job_ads.py` — scrapes jobs from 4+ APIs
- `extract_skills.py` — extracts skills from job descriptions
- `build_rag.py` — builds ChromaDB vector store
- `labeling_pipeline.py` — multi-label question classifier
- `answer_questions_local.py` — synthetic persona answer generator
- `validate_synthetic_output.py` — structural validation of annotations
- `quick_trust_check_local.py` — fast trust-check on a sample
- `audit_question_quality.py` — question quality audit
- `pipeline.py` — end-to-end pipeline orchestrator
- `create_visualizations.py` — generates distribution charts
- `verify_output.py` — validates labeled output

---

### Root level

**Added:**
- `requirements.txt` — moved from `data/requirements.txt`; Python deps for all data scripts
- `WORKFLOW_REDESIGN.md` — workflow redesign notes

**Removed:**
- `image.png` — deleted
- `PRESENTATION.md`, `PRESENTATION_NOTES.md` — deleted
- `presentation.html`, `presentation.html.backup` — deleted

**Updated:**
- `.gitignore` — added `data/jobs/chroma/` (ChromaDB generated binary store)

**Presentation artifacts** (kept):
- `presentation_charts/` — architecture diagram, pipeline charts (HTML + PNG)
- `presentation_charts.py` — chart generation script

---

## What was cleaned up during the merge

The following fixes were applied on the `vlad` branch before merging (commit `28a2f0d`):

- `data/src/` removed — scripts moved to `data/scripts/` (labeling_pipeline, create_visualizations, verify_output)
- `data/data/` removed — nested data dir; real `annotation_failures.jsonl` moved to `data/answers/`
- `data/answers/annotation_failures.jsonl` (empty 0-line file) replaced with real 8-line version
- `data/scripts/QUICK_TRUST_CHECK_README.md` + `VALIDATE_SYNTHETIC_OUTPUT_README.md` removed — absorbed into `data/scripts/README.md`
- `data/ADAPTIVE_QUESTIONNAIRE_INSTRUCTIONS.md` moved to `data/docs/`
- `data/requirements.txt` moved to project root as `requirements.txt`
- `data/models/.gitkeep` removed (README.md present)
- `data/jobs/chroma/` untracked from git (generated binary, now gitignored)
- README.md added to every `data/` subdirectory
