import { useAuth } from '../contexts/AuthContext'

// Role-gated rendering primitive (DEV-62). Renders `children` only when the
// signed-in user meets `role` (privilege-ordered — admin also satisfies a
// student gate); otherwise renders `fallback` (default: nothing).
//
// This is a UX affordance, NOT a security boundary — it just hides UI. Every
// protected action still calls a backend route guarded by require_role, which
// re-verifies the token and role server-side. Never rely on this alone to keep
// data or actions away from a non-privileged user.
//
// Usage:
//   <RequireRole role="admin">
//     <AdminPanelButton />
//   </RequireRole>
export default function RequireRole({ role = 'admin', children, fallback = null }) {
  const { hasRole, authLoading } = useAuth()
  if (authLoading) return fallback
  return hasRole(role) ? children : fallback
}
