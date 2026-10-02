# CLAUDE.md — Pathwise

Pathwise is a career development app: it sources roles, scores fit against
the operator's real experience, tracks skill gaps and a learning plan,
proposes projects, finds warm paths through the contact book, and drafts
outreach.

## Autonomy gate

Every outbound action goes through `requestAction()` in
`src/lib/autonomy.ts`. Actions that leave the app (email, form submission)
are held for review, and the global kill switch `OUTBOUND_SENDING` is
**off by default**: with it off, nothing is ever sent, whatever the action's
autonomy level. `/messages` drafts only; it has no send path. Email delivery
is off by default too. Marketing copy must never imply the app sends things
on its own.

## Copy

Every claim on the landing page must be true of the shipped product.
