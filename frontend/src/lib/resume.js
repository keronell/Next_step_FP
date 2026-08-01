// The resume pointer: which roadmap a returning user's next visit should open. It
// is remembered across page loads so `bootRedirect()` (hooks/useRoute.js) can act on
// it before React renders — see frontend/CLAUDE.md for why that decision happens
// there rather than after the history fetch.
//
// This module owns the pointer's whole lifecycle — the rule that derives it, and
// every write and clear — because both defects found against it were lifecycle gaps
// in code that knew the storage key but not the rules: a pointer that outlived an
// EXPIRED session (so the next account to sign in on that browser booted onto the
// previous account's career), and a pointer that outlived the submission it came
// from (so deleting your last assessment booted you onto a locked roadmap, every
// visit, permanently). Both were possible because "when is this still true?" lived
// nowhere in particular.

export const RESUME_CAREER_KEY = 'nextstep_resume_career'

// The career a set of submissions resumes to: the newest submission's explicit
// selection, else its top recommendation — the same rule behind the header's "My
// Roadmap" shortcut. Null when there is nothing to resume to, which is the answer
// that matters most: an empty history MUST produce null rather than "leave it as
// it was", or a deleted assessment's pointer survives it.
export function resumeCareerFrom(subs) {
  if (!subs?.length) return null
  const latest = [...subs].sort(
    (a, b) => new Date(b.created_at) - new Date(a.created_at),
  )[0]
  return latest.selected_career ?? latest.recommendations?.[0]?.id ?? null
}

// Write the pointer, or clear it when `careerId` is null. One function rather than a
// separate clear(): every caller that can produce a career can also produce "none",
// and splitting them is how a null ends up silently skipping the write instead of
// erasing a stale value.
export function setResumeCareer(careerId) {
  if (careerId) localStorage.setItem(RESUME_CAREER_KEY, careerId)
  else localStorage.removeItem(RESUME_CAREER_KEY)
}
