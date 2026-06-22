// Centralized backend client. The /questionnaire/submit response already matches
// the shape Results.jsx renders (id, title, description, keySkills, icon,
// roadmapKey, matchPercent) plus reasons/score_breakdown, so no remapping needed.

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export async function submitQuestionnaire(answers) {
  const res = await fetch(`${BASE_URL}/api/questionnaire/submit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ answers }),
  })

  if (!res.ok) {
    const err = new Error(`Request failed (${res.status})`)
    err.status = res.status
    throw err
  }

  const data = await res.json()
  return data.recommendations || []
}
