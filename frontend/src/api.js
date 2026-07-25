// Centralized backend client. All requests attach an auth token when one is
// present in localStorage (Bearer header). The anonymous session_id still rides
// along for correlation of anonymous submissions.

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

// Stable anonymous id per browser - correlates submission with career selection.
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
  if (res.status === 204) return null // No Content (e.g. DELETE) - nothing to parse
  return res.json()
}

// ── Questionnaire ────────────────────────────────────────────────────────────

// Question bank - the backend copy is authoritative; callers fall back to the
// bundled QUESTIONS in data.js when this fails (see Questionnaire.jsx).
export async function fetchQuestions() {
  return _request(`${BASE_URL}/api/questions`)
}

// `profile` is the optional DEV-60 self-input step. It rides inline so it reaches
// the matcher in the same request that produces these recommendations; omitted
// entirely when the user skipped the step (the backend then scores exactly as before).
export async function submitQuestionnaire(answers, profile = null) {
  const body = { answers, session_id: getSessionId() }
  if (profile && !isProfileEmpty(profile)) body.profile = profile
  const data = await _request(`${BASE_URL}/api/questionnaire/submit`, {
    method: 'POST',
    body: JSON.stringify(body),
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
// POST, not GET, because only the POST adds the job-ad market stages (DEV-59).
// It carries no body: roadmaps are curated and identical for every user, so there
// is nothing left to personalize with.
export async function fetchRoadmap(careerId) {
  return _request(`${BASE_URL}/api/roadmap/${careerId}`, { method: 'POST' })
}

// ── Self-input profile (DEV-60) ──────────────────────────────────────────────

export const EMPTY_PROFILE = { experience: [], projects: [], skills: [] }

export function isProfileEmpty(profile) {
  if (!profile) return true
  return !(profile.experience?.length || profile.projects?.length || profile.skills?.length)
}

// Both require auth. The profile is account data, so anonymous users never have one.
// `signal` lets callers bound the request - see Profile.jsx, where a write left
// running past its timeout could land after a newer one (storage is last-write-wins).
export async function fetchProfile(signal) {
  return _request(`${BASE_URL}/api/profile`, { signal })
}

// Returns the STORED profile, not what was sent - the server strips, dedupes and
// caps, so the caller should render what actually persisted.
export async function saveProfile(profile, signal) {
  return _request(`${BASE_URL}/api/profile`, {
    method: 'PUT',
    body: JSON.stringify(profile),
    signal,
  })
}

// Roadmap node completion - only for logged-in users (auth required by the API).
// Anonymous users keep progress in localStorage instead (see Roadmap.jsx).
export async function fetchRoadmapProgress(careerId) {
  return _request(`${BASE_URL}/api/roadmap/${careerId}/progress`)
}

export async function saveRoadmapProgress(careerId, completedNodes) {
  return _request(`${BASE_URL}/api/roadmap/${careerId}/progress`, {
    method: 'POST',
    body: JSON.stringify({ completed_nodes: completedNodes }),
  })
}

// ── Auth ─────────────────────────────────────────────────────────────────────

export async function signUp(email, password, username) {
  return _request(`${BASE_URL}/api/auth/register`, {
    method: 'POST',
    body: JSON.stringify({ email, password, username }),
  })
}

export async function signIn(email, password) {
  return _request(`${BASE_URL}/api/auth/login`, {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  })
}

// signOut is best-effort from the caller's side - AuthContext clears tokens
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

// The career ids the user was ever recommended, UNCAPPED — the roadmap unlock
// check (DEV-82). Distinct from fetchMySubmissions (capped at 20), which can't
// answer eligibility for a heavy user's older recommendation. Returns string[].
export async function fetchRecommendedCareers() {
  const { careers } = await _request(`${BASE_URL}/api/auth/recommended-careers`)
  return careers || []
}

// Delete one of the current user's submissions (auth required; the server enforces
// that the submission belongs to the caller). Resolves on 204, throws on 4xx/5xx.
export async function deleteSubmission(requestId) {
  return _request(`${BASE_URL}/api/auth/my-submissions/${encodeURIComponent(requestId)}`, {
    method: 'DELETE',
  })
}

// ── Admin (DEV-62) ───────────────────────────────────────────────────────────
// Both throw 403 for a non-admin caller — require_admin on the server is the gate,
// the hidden UI is only presentation.

export async function fetchAccounts() {
  return _request(`${BASE_URL}/api/admin/users`)
}

export async function deleteAccount(userId) {
  return _request(`${BASE_URL}/api/admin/users/${encodeURIComponent(userId)}`, {
    method: 'DELETE',
  })
}
