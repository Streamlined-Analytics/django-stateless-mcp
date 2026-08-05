# ADR-0037: Docs recommend OAuth (DOT + DCR) as the production default posture

- **Status:** Accepted
- **Date:** 2026-08-05
- **Builds on:** [ADR-0011](0011-bearer-auth.md) (bearer auth in the view),
  [ADR-0014](0014-user-and-tool-permissions.md) (user and tool permissions),
  [ADR-0029](0029-benefits-led-messaging.md) (benefits-led messaging),
  [ADR-0035](0035-concise-docs-link-out-no-adr-references.md) (concise docs
  that link out)

## Context

The docs presented authentication as a neutral menu: `usage.md`'s bearer-auth
section ended with "without a `token_verifier` the endpoint is open, and
protecting it is your project's responsibility — session auth behind
`login_required`, a private network, or whatever the deployment calls for."
Accurate, but it never said what a production deployment *should* do, and it
undersold the point that the package's access-control features —
`request.user` in tools, `user.has_perm(...)` gating, `PermittedToolsFilter`
visibility — only become meaningful when requests are authenticated. An open
endpoint serves every caller as `AnonymousUser`; the permission layer the
package is proudest of sits dark.

The OAuth & permissions recipe already wired the full stack
(django-oauth-toolkit as the in-project authorization server,
django-oauth-toolkit-dcr for Dynamic Client Registration, `user_resolver`
into `request.user`) but opened as a neutral how-to, without saying that this
is the recommended production posture or why DCR matters (MCP clients
register themselves; no hand-issued client credentials).

## Decision

State the recommendation explicitly, in the two places a reader decides:

- **`usage.md` (Requiring bearer authentication)** — the open-endpoint
  paragraph now reads "fine in development, rarely right in production",
  names the DOT + DCR pairing, and frames authentication as what "switches
  on the rest of the package's power", linking the recipe for the wiring.
- **The OAuth & permissions recipe** — opens with "the posture to default to
  in production" and a four-bullet benefits outline: per-request
  authentication (401/403 semantics), a real Django user from the verified
  token, per-tool access control (gating + visibility), and self-onboarding
  clients via DCR.

The recommendation is worded as a strong default ("rarely right in
production"), not an absolute — private-network and session-fronted
deployments remain legitimate, and the view continues to serve open endpoints
without complaint. Enforcement stays out of the package: this is
documentation posture, not a runtime warning, consistent with the
foundation-not-product stance.

## Consequences

- Readers reaching the auth section get a direct answer to "what should I do
  in production?" instead of a menu, and the permissions features are framed
  as the payoff of authenticating rather than an unrelated extra.
- The docs now name a specific third-party pairing (DOT + DCR). If the
  ecosystem's answer to MCP dynamic client registration changes, both
  paragraphs and the recipe must move together.
