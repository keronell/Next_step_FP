// Minimal dependency-free path router. The app is otherwise a single-page phase
// machine (no react-router); this adds just enough to give the roadmap its own
// addressable URL (DEV-65's `/roadmap/{id}` intent) so a returning user can deep-
// link straight to it (DEV-76), while every other path renders the scroll app.
//
// navigate() drives programmatic pushes; the browser Back button is handled via
// the native `popstate`. Both funnel through a private `nextstep:navigate` event
// so every useRoute() consumer re-renders on a same-tab push (pushState alone
// fires no event).
import { useEffect, useState } from 'react'
import { CAREERS } from '../data'

const NAV_EVENT = 'nextstep:navigate'

// Allowlist of valid roadmap ids (the bundled career catalog — kept in sync with
// the backend per CLAUDE.md). The decoded segment MUST be one of these, so a
// crafted path like `/roadmap/..%2Fauth%2Flogout` (which decodes to
// `../auth/logout` and would otherwise be interpolated into API URLs) never
// matches the route.
const CAREER_IDS = new Set(CAREERS.map((c) => c.id))

// Programmatic navigation: push the URL, scroll to top, notify consumers.
export function navigate(path) {
  if (path === currentPath()) return
  window.history.pushState({}, '', path)
  window.scrollTo(0, 0)
  window.dispatchEvent(new Event(NAV_EVENT))
}

// Rewrite the CURRENT history entry to home, creating none. For neutralizing an
// entry the app has decided not to honor (see App's mid-run roadmap guard):
// replaceState alone would leave useRoute's path stale — and the app rendering
// off a route the URL bar no longer shows — so notify consumers like navigate does.
export function replaceWithHome() {
  window.history.replaceState({}, '', '/')
  window.dispatchEvent(new Event(NAV_EVENT))
}

function currentPath() {
  return window.location.pathname
}

// A scroll-app section id a nav control asked for that wasn't mounted at click
// time (e.g. every #section while the standalone roadmap route is showing). The
// scroll app consumes and honors it once it mounts — see consumePendingScroll().
let pendingScrollId = null

// Scroll to a scroll-app section by id. If it's on the current page, scroll now;
// otherwise remember it and route home, so the control still performs its labeled
// action (jump to that section) instead of just dumping the user at the top.
export function navigateToSection(id) {
  const el = document.getElementById(id)
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'start' })
    return
  }
  // Not on this page. If we're already home the section simply isn't rendered
  // (e.g. a gated one) — nothing to defer; clear so it can't fire later.
  if (currentPath() === '/') {
    pendingScrollId = null
    return
  }
  pendingScrollId = id
  navigate('/')
}

// Read-and-clear the pending section target. Returns null when there's none.
export function consumePendingScroll() {
  const id = pendingScrollId
  pendingScrollId = null
  return id
}

// Returns the `careerId` for `/roadmap/:careerId` when it decodes to a known
// career id, else null. Trailing slashes and empty segments are "no match". A
// malformed percent-encoded segment (e.g. `/roadmap/%E0%A4%A`) makes
// decodeURIComponent throw, and a crafted one (e.g. `/roadmap/..%2Fauth%2Flogout`)
// decodes to a path-traversal string; both are rejected here so the path just
// falls through to the normal scroll app rather than blanking it or reaching an
// unintended API endpoint.
export function matchRoadmap(pathname) {
  const m = pathname.match(/^\/roadmap\/([^/]+)\/?$/)
  if (!m) return null
  let id
  try {
    id = decodeURIComponent(m[1])
  } catch {
    return null
  }
  return CAREER_IDS.has(id) ? id : null
}

// Subscribe to the current pathname, re-rendering on Back/forward (popstate) and
// on programmatic navigate() (NAV_EVENT).
export function useRoute() {
  const [path, setPath] = useState(currentPath())

  useEffect(() => {
    const onChange = () => setPath(currentPath())
    window.addEventListener('popstate', onChange)
    window.addEventListener(NAV_EVENT, onChange)
    return () => {
      window.removeEventListener('popstate', onChange)
      window.removeEventListener(NAV_EVENT, onChange)
    }
  }, [])

  return path
}
