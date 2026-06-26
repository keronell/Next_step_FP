// Centralized backend client. All requests attach an auth token when one is
// present in localStorage (Bearer header). The anonymous session_id still rides
// along for correlation of anonymous submissions.

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

// Stable anonymous id per browser — correlates submission with career selection.
export function getSessionId() {
  let id = localStorage.getItem('nextstep_session_id')
  if (!id) {
    id = crypto.randomUUID?.() || `s-${Date.now()}-${Math.random().toString(36).slice(2)}`
    localStorage.setItem('nextstep_session_id', id)
  }
  return id
}

function getAccessToken() {
  return localStorage.getItem('nextstep_access_token')
}

function authHeaders() {
  const token = getAccessToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

// Shared fetch wrapper: adds auth + Content-Type, throws on non-2xx.
async function _request(url, options = {}) {
  const res = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
      ...(options.headers || {}),
    },
  })
  if (!res.ok) {
    const err = new Error(`Request failed (${res.status})`)
    err.status = res.status
    try { err.body = await res.json() } catch {} // eslint-disable-line no-empty
    throw err
  }
  return res.json()
}

// ── Questionnaire ────────────────────────────────────────────────────────────

export async function submitQuestionnaire(answers) {
  const data = await _request(`${BASE_URL}/api/questionnaire/submit`, {
    method: 'POST',
    body: JSON.stringify({ answers, session_id: getSessionId() }),
  })
  return data.recommendations || []
}

// Fire-and-forget: record which career the user opened. Never blocks the UI.
export function selectCareer(careerId) {
  fetch(`${BASE_URL}/api/questionnaire/select`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ session_id: getSessionId(), career_id: careerId }),
  }).catch(() => {})
}

// Fetch + optionally personalize a career roadmap via the backend.
export async function fetchRoadmap(careerId, missingSkills = []) {
  return _request(`${BASE_URL}/api/roadmap/${careerId}`, {
    method: 'POST',
    body: JSON.stringify({ missing_skills: missingSkills }),
  })
}

// ── Auth ─────────────────────────────────────────────────────────────────────

export async function signUp(email, password) {
  return _request(`${BASE_URL}/api/auth/register`, {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  })
}

export async function signIn(email, password) {
  return _request(`${BASE_URL}/api/auth/login`, {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  })
}

// signOut is best-effort from the caller's side — AuthContext clears tokens
// regardless of whether this call succeeds.
export async function signOut() {
  return _request(`${BASE_URL}/api/auth/logout`, { method: 'POST' })
}

export async function getMe() {
  return _request(`${BASE_URL}/api/auth/me`)
}

// Link prior anonymous session_id rows to the now-authenticated user.
export async function claimSessions() {
  return _request(`${BASE_URL}/api/auth/claim-sessions`, {
    method: 'POST',
    body: JSON.stringify({ session_id: getSessionId() }),
  })
}

export async function fetchMySubmissions() {
  return _request(`${BASE_URL}/api/auth/my-submissions`)
}
