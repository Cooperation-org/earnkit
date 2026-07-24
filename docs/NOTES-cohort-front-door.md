# Cohort front door / post-login connect chain — handoff note

Status 2026-07-24. Env is set correctly here; the remaining fix is CODE in other repos.

## What's wired (env / earnkit — done)
GovKit `COHORT_FRONT_DOOR` controls where a member lands after LinkedTrust login
(else GovKit dumps them on its own `/o/` org-list — the "flicker").

- group_vars `govkit_cohort_front_door` → renders `COHORT_FRONT_DOOR` in govkit `.env`.
- `{org_slug}` is a LITERAL placeholder GovKit `.format()`s per member's org — NOT
  hardcoded to any team. Every member lands on their OWN org's dash.

## The bug that broke sign-in (CODE — other session)
Intended chain: login → `workers.vc/dash/<org>/connect/` (workersvc) →
`crm-<org>.workers.vc/outreach/connect` (Odoo) → back to `/dash/<org>/`.

The CRM hop **404s**: `/outreach/connect` does not exist in the Odoo
`crm_outreach_runner` addon. So pointing the front door at `.../connect/` sends
members to a 404 → broken sign-in.

## Interim (env — in place now)
`COHORT_FRONT_DOOR=https://{{ workersvc_domain }}/dash/{org_slug}/` — skips the
connect hop, lands members straight on the working dash (200; cards load
client-side). Per-org, no hardcoding.

## Correct fix (CODE — please do on dev, not prod)
Pick one, then flip the front door back to `.../dash/{org_slug}/connect/`:
1. Implement `/outreach/connect` in Odoo `crm_outreach_runner` (the CRM identity
   bridge the connect page expects), OR
2. Make workersvc's `/dash/<org>/connect/` resilient when the CRM route isn't
   present (fall through to the dash instead of redirecting into a 404).

Repos: workersvc (connect route), Odoo `crm_outreach_runner` (the 404 route).
