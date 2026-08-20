# Cohort stack index — every surface, flow, and interface

2026-07-19. What exists across the composed repos, so nothing gets rebuilt or
lost. Verified against code and the live deployment this date. Companion to
`PLAN-cohort-dash.md` (same-named file in each repo). Corrections welcome —
this file lives in earnkit because earnkit is the composition.

> **Manual state on the live box:** amebo's team CRM/Taiga connections and the
> `odoo-cli` install were provisioned **by hand** on cohort-services on
> 2026-08-20 (inventory-local predates the service-account feature). What was
> done, where the creds live, and the known gaps are recorded in
> [`docs/COHORT-MANUAL-STATE-2026-08.md`](docs/COHORT-MANUAL-STATE-2026-08.md).

## Hosts (live cohort VM, via Caddy-on-Proxmox → VM nginx)

| Host | App | Repo | Upstream |
|---|---|---|---|
| `workers.vc` (+www) | doorway/landing/wall/dash (Django "workersvc") | Cooperation-org/workers.vc | 127.0.0.1:8015 |
| `dash.workers.vc` | GovKit (multitenant, one org per team) | Cooperation-org/govkit | 127.0.0.1:8010 |
| `amebo.workers.vc` | amebo backend (+ `/embed/amebo.js`) | Cooperation-org/amebo | 127.0.0.1:8000 |
| `taiga.workers.vc` | Taiga (API + events + static) | taiga-back/-front (upstream) | 127.0.0.1:8080 |
| `marten.workers.vc` | Marten (SvelteKit static Taiga frontend) | Cooperation-org/marten | nginx static `/opt/marten/src/build` |
| `crm-<team>.workers.vc` | Odoo 17 CRM, one DB per team (`crm-<team>`, dbfilter `^%d$`; no bare `crm.` host) | odoo + crm-card-scanner + crm-outreach-runner | 127.0.0.1:8069 (ws 8072) |
| `live.linkedtrust.us` | OIDC IdP for every app + the claims backend (`LT_API`) | (LinkedTrust) | external |
| `amebo.linkedtrust.us` / `api.amebo.linkedtrust.us` | LinkedTrust's own amebo (reference frontend: key-links bar + campaigns board) | same amebo repo | external |
| `demos.linkedtrust.us/workersvc-design/dashboard.html` | v3 cohort-dash design spec (static) | — | external |

## workers.vc — the doorway (public face + wall + cohort dash)

Routes (`workersvc/urls.py`):
- `/` — landing + commitment wall, grouped by role; `?committed=<id>` share card, `?pending` banner. GA4 on this page only.
- `/commit/` — walk-up join page. Role picker (founder/funder/mentor). POST creates a LinkedTrust `COMMITS_TO` claim; walk-ups start pending (admin approves). **Mentor variant prompts for calendar booking link + time level** — stored in the local ledger (`EarnedgovCommitment.calendar_url`, `time_level`). Photo/video upload, browser-side compression.
- `/opportunities/` — adoptable `OPPORTUNITY` claims board.
- `/card/<claim_id>.png` — server-rendered 1200×630 og:image share card (PIL).
- `/dash/` — unified cohort dash (read-only cards; growing into the v3 spec — see PLAN).
- `/i/<code>/` — **invite doorway**: resolves a GovKit-minted invite via S2S, lands the invitee on the join page prefilled (mentor invites → calendar prompt included); commit auto-approves to the wall (link possession = spam gate), reports the claim back to GovKit, then hands them GovKit's `accept_url`.
- `/admin/` — moderation queue (approve → issues a `VALIDATES` "Approved" claim; hide).

Integrations: `doorway/claims.py` (LinkedTrust: COMMITS_TO/VALIDATES/OPPORTUNITY, wall filter checks server-stamped issuer), `doorway/govkit.py` (S2S invite resolve/report, bearer `GOVKIT_S2S_TOKEN`), `doorway/amebo.py` (links for the dash tools row; user JWT until amebo API keys land).
Local state: ONLY the moderation ledger. Design: CDN Tailwind marketing pages + the dash's own light/dark CSS-variable system.

## govkit (dash.workers.vc) — earned governance

HTML (org-scoped `/o/<slug>/…`): dashboard (venture orgs: **genesis checklist** — 5 modules: Exist / Who's it for / Build / Money / Receipts), drops, pie, votes, committee (sortition), tasks, projects, members (admin: roles, rates, **invite mint**, invite ledger). Non-org: `/` org picker, `/onboarding/`, `/invites/<code>/accept/`.

JSON API `/api/v1/…` (DRF, session auth, org-gated by middleware; CORS for allowlisted origins as of 2026-07-19):
- `accounts/me/` — identity + memberships (the mentor/org-switcher feed)
- `pie/orgs/<slug>/summary/` (slices→lines→tasks drill-down) and `standing/`
- `tasksources/orgs/<slug>/tasks/` (DONE tasks only — valuation pipeline), `sync/`
- `drops/…`, `votes/…`, `sortition/…`, `exports/…` (incl. Slicing Pie CSV), `projects/…` (**money**: Project/Deal/Split/Payout + per-project summary)
- `orgs/…` (orgs, members, invites admin) + **S2S invite pair** for the doorway: `GET/POST /api/v1/orgs/<slug>/invites/<code>[/committed/]` (bearer token)
- Cohort-dash additions (shipped 2026-07-19): `orgs/<slug>/checklist/` JSON, `tasksources/orgs/<slug>/tasks/open/` (live Taiga proxy), `projects/orgs/<slug>/portfolio/`, and the `static/embed/govkit.js` web-components bundle (+ demo page); login honors allowlisted `?next=`.

Invites (`apps/orgs/invites.py`, `models.Invite`): single-use stateful codes, statuses created→committed→accepted / revoked, expiry; audiences advisor/mentor/partner/funder/founder/supporter; founder invites carry venture_name → accept creates the venture org + seeds the checklist; accept reports membership to amebo (`/api/orgs/provision`).
**Shipped 2026-07-19:** ONE flow — the per-invite doorway checkbox is gone (doorway whenever configured); mint form grouped (founder venture fields only for founder audience); invite ledger owns copyable links + revoke; anonymous accept renders the **door** — magic-link = bearer capability: "Count me in" creates the account (email from invite or typed) with no OAuth; never signs into an existing account; an existing member opening a link (inviter preview) never consumes it.
Auth: LinkedTrust OIDC (primary), Google, dev-login seam. Multitenancy: Org / Membership(admin·steward·member) / OrgScoped models; superuser sees all. Task sources: Taiga adapter only (encrypted org API token). Design: `static/govkit.css` + `docs/design/pattern-language.md` (warm paper, hairline, leaves, status-is-a-word).

## amebo (amebo.workers.vc) — team knowledge agent

- Embed components (`embed/amebo.js`, served at `/embed/amebo.js`; vanilla JS, `data-up`, cookie `credentials:'include'`): `<amebo-ask>`, `<amebo-goal>`, `<amebo-digest>`, `<amebo-claws>`, `<amebo-create-claw>`. Org resolved server-side, never an attribute.
- API highlights: `/api/qa/ask`, `/api/digest`, `/api/organizations/{me,users,stats,links,board}` (links = `instances.config.links`, the dash tools row; board = campaigns from the org context repo), `/api/goals/*` (JWT **or** X-API-Key), `/api/orgs/provision` (S2S bearer, used by GovKit accept + add-team), team management, chat, whiteboard, pending-actions, connections.
- Auth: session JWT (localStorage) via LinkedTrust OIDC (`/api/auth/oidc/login`) or Google or password; X-API-Key service keys; AuthGate on the public edge. CORS origins from `CORS_ORIGINS` env.
- Frontend (Next.js, amebo.linkedtrust.us): `/dashboard` = key-links bar + campaigns board (the orientation-surface principle, docs/DASHBOARD.md), plus chat, whiteboard, Q&A, workspaces, team, approvals, connections, needs-input.
- Slack: `/ask`, `/askall`, `/task <project> <subject> due:… [assign:…] [cash:N]` (creates Taiga task directly), `@amebo` mention → gated agentic path. **No hours-logging command exists.**
- Multitenancy: instances ⟂ orgs (`instance_orgs`), org context repo (`organizations.context_repo`) declares tool bindings + campaigns.

## marten (marten.workers.vc) — Taiga frontend

Routes: `/login` (LinkedTrust server-side OIDC primary, Google, Bluesky/ATProto, password), `/p/<slug>/board|backlog|epics|velocity`, `/tasks` (cross-project My Tasks), OAuth callbacks. Deep links: `/p/<slug>/board?story=<ref>`.
Taiga API: Bearer JWT, refresh, wide-open CORS on taiga-back — external pages can call it with a token.
Known gaps: register tab calls a method that doesn't exist (throws), dead client-side OIDC helper still imported, stale NOTES/README, no login round-trip back to deep links (bounces to `/login`). See PLAN.

## CRM addons (per-team Odoo)

- `crm_card_scanner`: Contacts → Scan Card (phone camera → MiniMax vision or local Tesseract → `res.partner` + card image; company find-or-create). `/scan-card` redirect route. No lead creation.
- `crm_outreach_runner`: CRM → Outreach Runner — prioritized `crm.lead` queue: pin/drag beats stored rubric `outreach_score` (0-100 + reason), "Contacted" stamps `last_outreach_date`; partner linkedin/discord fields. **No HTTP/JSON API yet** (planned: `/outreach/api/queue` + `<crm-reachout>`, see its PLAN).
- `crm_world`: the world model — `world.space` (a place with membership you enter and are heard in: slack, discord, forum, list, repo, venue, city) and `world.event` (happens at a time, not ours to move: conference, call, application window, funding deadline), with `world.event.date` holding each dated moment so "the next six weeks" is one indexed query. Contacts attach as speakers/attendees/members; `res.partner` gains a World tab. Both carry `uri` (how the world names it) and `last_verified` (a claw must own refreshing it). No lead time on the event by design — when a thing surfaces is the sorting rubric's call, not the fact's.
- Two more addons exist only on the old live CRM VM, not in git: `crm_relationship_dashboard`, `quick_outreach`.
- OIDC: `auth.oauth.provider` row per team DB, created by add-team.yml (implicit flow).

## earnkit — composition (this repo)

- `site.yml`: base → rabbitmq → taiga → marten → odoo → amebo → agent-clis → govkit → workersvc → nginx → cicd. All state on external Postgres (`database_host`).
- `playbooks/add-team.yml -e team_slug=… -e team_name=…` — per-team: Odoo DB `crm-<slug>` + modules + OIDC row + Caddy route, Taiga private project (slug=team), amebo instance row + org provision (S2S), GovKit org. People are NEVER provisioned here — that's amebo's job via GovKit accept.
- CI/CD: each app repo's `deploy-to-cohort.yml` → ssh `deploy` user → `sudo /opt/earnkit/bin/update-{workersvc,govkit,amebo,marten}` (reset to origin/main, deps, migrate, restart). Taiga/Odoo update by playbook re-run only.
- docs: DECISIONS.md (hostname scheme, per-service multitenancy, no docker), SSO-AND-TEAMS.md (identity = OIDC sub; membership sync partly unbuilt; launch-gate notes).
- KNOWN ISSUE: the real inventory commits live secrets in plaintext, against its own rule.

## Cross-cutting flows

1. **Walk-up join**: `/commit/` → claim on LinkedTrust → pending → admin approves (approval claim) → wall.
2. **THE invite flow — there is exactly one**: GovKit members page mints → share `workers.vc/i/<code>/` → join page prefilled (**mentors: calendar prompt here**; their words, image/video) → commit = auto-approved wall entry + claim reported to GovKit → GovKit accept step, now zero-friction: signed-in joins instantly; anonymous gets the door — "Count me in" creates the account from the invite email (or typed), no OAuth; existing email routes through sign-in; link possession never unlocks an existing account. Founder invites spawn the venture org + checklist on accept; amebo provisions the member across tools. Invites are revocable until accepted; an existing member opening a link (inviter previewing) never consumes it. Login is optional by design — the inviter's trust is the gate.
3. **Team provisioning**: add-team.yml (see above). Org slug is the tenant key everywhere (GovKit org, amebo org, Taiga project slug, `crm-<slug>` host and DB).
4. **SSO**: LinkedTrust OIDC on every app (currently one shared client id). Sessions are per-app (GovKit Django cookie, amebo JWT, Taiga JWT, Odoo session); one IdP session makes the per-app logins quiet.
5. **Cohort dash** (`workers.vc/dash/`): read-only cards, each owned by its app via web components + credentialed CORS — the whole contract is in the six `PLAN-cohort-dash.md` files.
6. **Deploys**: push to main → auto-deploy (workersvc/govkit/amebo/marten); env/config and Odoo/Taiga → ansible.
