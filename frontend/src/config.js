// Build-time flags.
//
// REQUIRE_AUTH gates the assessment behind login. Set VITE_REQUIRE_AUTH=false in
// the build environment (e.g. the standalone Vercel demo) to bypass the login
// gate so the full assessment -> results -> roadmap flow runs with no backend.
// Defaults to true, so normal dev/prod behavior is unchanged.
export const REQUIRE_AUTH = import.meta.env.VITE_REQUIRE_AUTH !== 'false'
