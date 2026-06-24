// Centralized backend client. The /questionnaire/submit response already matches
// the shape Results.jsx renders (id, title, description, keySkills, icon,
// roadmapKey, matchPercent) plus reasons/score_breakdown, so no remapping needed.

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

// Stable anonymous id per browser, so a submission and the career the user later
// picks can be correlated server-side. crypto.randomUUID is available in all
// browsers we target (and falls back to a timestamp id if somehow absent).
export function getSessionId() {
  let id = localStorage.getItem('nextstep_session_id')
  if (!id) {
    id = crypto.randomUUID?.() || `s-${Date.now()}-${Math.random().toString(36).slice(2)}`
    localStorage.setItem('nextstep_session_id', id)
  }
  return id
}

export async function submitQuestionnaire(answers) {
  const res = await fetch(`${BASE_URL}/api/questionnaire/submit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ answers, session_id: getSessionId() }),
  })

  if (!res.ok) {
    const err = new Error(`Request failed (${res.status})`)
    err.status = res.status
    throw err
  }

  const data = await res.json()
  return data.recommendations || []
}

// Fire-and-forget: record which career the user opened. Never blocks the UI, so
// failures (backend down) are swallowed — tracking is best-effort.
export function selectCareer(careerId) {
  fetch(`${BASE_URL}/api/questionnaire/select`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: getSessionId(), career_id: careerId }),
  }).catch(() => {})
}

// Fetch a career's roadmap ({ sections: [...] }). POSTs the user's missing skills so
// the backend can personalize via LLM (falls back server-side to static if OpenAI is
// off). Throws on failure so callers can fall back to the bundled client-side ROADMAPS.
export async function fetchRoadmap(careerId, missingSkills = []) {
  const res = await fetch(`${BASE_URL}/api/roadmap/${careerId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ missing_skills: missingSkills }),
  })
  if (!res.ok) throw new Error(`Roadmap request failed (${res.status})`)
  return res.json()
}
