# Cohort Dash — cross-repo plan (earnkit copy)

2026-07-19. One of six coordinated plan files, one per repo:
`workers.vc`, `govkit`, `amebo`, `marten`, `crm-outreach-runner`, `earnkit` —
each named `PLAN-cohort-dash.md` at the repo root. The **Architecture**
section is identical in all six; the **This repo** section is per-repo.
Work in parallel; commit and push regularly; each repo only implements its
own section and consumes the others' contracts as written here.

## Architecture (shared across all six repos)

**Goal.** Land accelerator teams on a real dashboard: the v3 design
(demos.linkedtrust.us/workersvc-design/dashboard.html) grown out of the
existing `/dash/` page, plus a mentor view, so invites can go out now.

**Principle** (amebo docs/DASHBOARD.md): the dash is an orientation
surface, not a workspace. Every fact lives in the tool that owns it; the
dash renders read-only cards and every card expands into the owning app
(Marten, GovKit, CRM, amebo). No fact is copied into the dash's DB.

**Mechanism: web components, one bundle per owning app.** Following the
existing amebo embed pattern (`amebo/embed/amebo.js`): each app ships a
vanilla-JS custom-elements bundle as a static file from its own origin.
The dash page includes the scripts and mounts the tags. No build step, no
framework, no shared library.

**Auth: SSO + same-site cookies + CORS allowlist.** Everything runs under
`*.workers.vc`, and every app logs in via LinkedTrust OIDC
(live.linkedtrust.us). Because all hosts share the registrable domain
`workers.vc`, each app's `SameSite=Lax` session cookie IS sent on a
credentialed fetch from the dash page — the only missing layer is CORS
response headers. So each app: (1) allowlists `https://workers.vc` (and
`https://www.workers.vc`) for CORS **with credentials**, scoped to its
JSON API paths; (2) authenticates component fetches with its normal
session cookie (`credentials: 'include'`). A component whose upstream
returns 401/403 renders nothing (the existing dash behavior) — signed-out
or non-member visitors just see fewer cards. Never render placeholder or
demo data.

**Org scoping.** The dash is per-team: `workers.vc/dash/<org-slug>/`.
The org slug is the shared tenant key across GovKit (`Org.slug`), amebo
(`organizations.slug` / instance orgs), Taiga (project slug), and Odoo
(DB `crm-<slug>`, host `crm-<slug>.workers.vc`) — provisioned together by
`earnkit/playbooks/add-team.yml`. Components take the org via a
`data-org` attribute where the owning app needs it (GovKit), or resolve
it server-side from the authenticated identity (amebo — org is never a
component attribute there).

**Card → owner map** (v3 design → who ships the component):

| Card | Owner | Component | Expand target |
|---|---|---|---|
| The pie | GovKit | `<govkit-pie>` | `dash.workers.vc/o/<org>/pie/` |
| Earned on tasks (hours feed) | GovKit | `<govkit-feed>` | `dash.workers.vc/o/<org>/pie/` |
| Curriculum tracker | GovKit (genesis checklist) | `<govkit-checklist>` | `dash.workers.vc/o/<org>/` |
| Tasks to do | GovKit (tasksources → Taiga) | `<govkit-tasks>` | `martin.workers.vc/p/<org>/board` |
| Money | GovKit (projects app) | `<govkit-money>` | `dash.workers.vc/o/<org>/projects/` |
| Reach out (CRM) | crm-outreach-runner (Odoo) | `<crm-reachout>` | `crm-<org>.workers.vc` Outreach Runner |
| Ask amebo | amebo (exists) | `<amebo-ask>` | `amebo.workers.vc` |
| Campaigns / GTM board | amebo (`/api/organizations/board`) | `<amebo-board>` (phase 2) | org context repo / CRM / Taiga links |
| Whiteboard | amebo (phase 2) | — | amebo whiteboard |
| Tools row, faces, launch card | workers.vc server-side | — | — |

**Mentors.** No new role system. A mentor is a person with GovKit
`Membership` rows in multiple orgs (the accelerator org plus team orgs).
`GET dash.workers.vc/api/v1/accounts/me/` already returns
`memberships[{org_slug, org_name, role}]` — the dash uses it (via the
same CORS/session mechanism) to render an org switcher and a mentor
overview listing every org the viewer belongs to. Mentor booking info
(calendar_url/time_level) already lives in workers.vc's ledger.

**Deploys.** Push to main deploys workers.vc / govkit / amebo / marten
via GitHub Actions → `/opt/earnkit/bin/update-*` (service restart). Odoo
addons and nginx/env changes deploy by ansible run (see earnkit plan).

**Sequencing.** GovKit's CORS + bundle is the critical path (4 of the 8
cards); everything else proceeds in parallel against these contracts, and
each card goes live the moment its owner ships.

---

## This repo: earnkit — env plumbing for the contracts above

No topology change: `dash.workers.vc` stays GovKit; the cohort dash page
stays on the apex (`workers.vc/dash/<org>/`) served by workersvc. All
work here is env/template plumbing for the other repos' items, applied
by playbook run (config changes don't ride the git-push CI).

### Work items

1. **govkit.env.j2** — add GovKit's CORS origins (new var, e.g.
   `govkit_cors_origins`, cohort value
   `https://workers.vc,https://www.workers.vc`) once govkit reads
   `CORS_ALLOWED_ORIGINS` from env (govkit plan item 1).
2. **amebo.env.j2** — set
   `CORS_ORIGINS=https://workers.vc,https://www.workers.vc,https://amebo.workers.vc`
   (amebo plan item 2; today the default origin list applies because the
   env never sets it).
3. **workersvc.env.j2** — add the browser-facing vars the dash template
   needs: `GOVKIT_PUBLIC_URL=https://dash.workers.vc`,
   `AMEBO_PUBLIC_URL=https://amebo.workers.vc`, and the marten public
   URL `https://martin.workers.vc` (name per workers.vc plan item 8);
   later the amebo links API key replacing the personal-JWT
   `AMEBO_API_TOKEN` (amebo plan item 3).
4. **Odoo module upgrade path** — the outreach endpoint (crm plan) needs
   `-u crm_outreach_runner` on every team DB after the addon updates:
   add a small playbook or extend the odoo role with an
   `upgrade-crm-addons` task that loops team DBs (source of truth for
   the team list: the `crm-*` databases themselves), so addon updates
   are one command instead of hand-run odoo-bin.
5. **After each app change lands**: run the corresponding role/playbook
   and verify with a credentialed curl from the VM (Origin header set)
   that CORS headers come back on govkit + amebo APIs.

### Notes for the operator (from 2026-07-19 research; not part of this
plan's scope, decide separately)

- `inventory/workers-vc/group_vars/all.yml` currently commits live
  secrets (DB admin password, OIDC client secret, S2S tokens, a private
  SSH key, caddy token) in plaintext, contrary to DECISIONS.md's
  "no secrets in git" rule.
- `marten_domain` is `martin.workers.vc` (spelling) — everything in
  these plans uses `martin.` to match what's deployed.
- SSO-AND-TEAMS.md flags amebo's `LEGACY_ENV_ORG_ID` unscoped fallback
  as a launch-gate item before a second org exists.

### Definition of done

A playbook run applies all env changes idempotently; credentialed
preflight + GET from origin `https://workers.vc` succeeds against
`dash.workers.vc/api/v1/...` and `amebo.workers.vc/api/...`; one command
upgrades the outreach addon across all team CRM DBs.
