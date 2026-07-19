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
(DB `crm-<slug>_vc`, host `crm-<slug>.workers.vc`) — provisioned together by
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

1. **DONE 2026-07-19 — govkit.env.j2**: new site var
   `govkit_cors_origins` (defined in group_vars, derived
   `https://{{ workersvc_domain }},https://www.{{ workersvc_domain }}`
   → the cohort value) renders `CORS_ALLOWED_ORIGINS=`; inert until
   govkit adds django-cors-headers (govkit plan item 1). Empty default
   in role defaults keeps older inventories rendering.
2. **DONE 2026-07-19 — amebo.env.j2**: new site var `amebo_cors_origins`
   (group_vars, derived → the cohort value incl. `https://amebo.workers.vc`)
   renders `CORS_ORIGINS=`; empty/unset omits the line so amebo's
   built-in default origin list still applies.
3. **DONE 2026-07-19 — workersvc.env.j2**: renders
   `GOVKIT_PUBLIC_URL=https://{{ govkit_domain }}`,
   `AMEBO_PUBLIC_URL=https://{{ amebo_domain }}`,
   `MARTEN_PUBLIC_URL=https://{{ marten_domain }}` (name follows the
   settings' `*_PUBLIC_URL` convention — workers.vc plan item 8 names
   the first two and leaves the marten one to convention; value keeps
   the deployed `martin.` spelling via `marten_domain`). Also now
   templates `AMEBO_API_BASE` + `AMEBO_API_TOKEN`
   (`workersvc_amebo_api_token`, personal JWT) so a playbook run no
   longer clobbers the hand-set token; commented for replacement by an
   amebo API key when amebo plan item 3 lands.
4. **DONE 2026-07-19 — Odoo module upgrade path**:
   `playbooks/upgrade-crm-addons.yml` →
   `roles/odoo/tasks/upgrade-addons.yml`. Discovers team DBs at runtime
   (`pg_database` matching `^crm-[a-z0-9-]+_vc$`; never a hardcoded
   list; base `crm_vc` deliberately excluded) and runs odoo-bin
   `-u {{ odoo_upgrade_modules }}` (defaults to every custom addon;
   `-e odoo_upgrade_modules=crm_outreach_runner` narrows) with
   `--stop-after-init --no-http` on each. One command; safe to re-run.
5. **OPERATOR — next action, not yet run**: after each app change lands,
   run the corresponding role/playbook against the live inventory and
   verify with a credentialed curl from the VM (Origin header set) that
   CORS headers come back on govkit + amebo APIs. New group_vars to add
   to the live inventory first: `govkit_cors_origins`,
   `amebo_cors_origins`, `workersvc_amebo_api_token` (move the current
   hand-set dash-tools JWT here), and the two `workersvc_lt_client_*`
   vars now also documented in the example inventory.

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
