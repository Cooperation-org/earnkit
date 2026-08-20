# Cohort-services manual provisioning — amebo team connections (2026-08-20)

**Where you are looking:** this file records changes made **by hand** on the
live cohort VM (cohort-services, 10.0.0.17). earnkit is the RECORD of the box,
not something re-applied over it — so what was done manually is written here so
it is not lost. Nothing below was applied by a full `site.yml` run.

Why by hand: the live `/opt/earnkit/stack/inventory-local` was rendered before
the amebo service-account feature (commit 39edbd1), so it has **none** of the
`amebo_odoo_service_*` / `amebo_taiga_service_*` credentials, and the runner
template (`roles/runner/templates/inventory-group-vars.yml.j2`) does not render
them either. `refresh-team.yml` therefore could not get them from inventory;
they were passed on the command line for the runs below.

## 1. amebo Odoo service login — DONE, all 6 team CRM dbs

`res.users` login `amebo`, active, groups `base.group_user` +
`sales_team.group_sale_salesman_all_leads` + `base.group_partner_manager`,
created in: **crm-vc, crm-demo-org-try-things-here, crm-integralmass,
crm-healthdocx, crm-trusthire, crm-amerissa-studio**. Done by running
`playbooks/refresh-team.yml -e team_slug=<slug> -e team_name='<Name>'` (plus the
service-account vars on the CLI).

Credential lives in **`/opt/amebo/backend/.env`** (root/amebo only):
`ODOO_USER=amebo`, `ODOO_API_KEY=<password>`, `ODOO_URL=http://127.0.0.1:8069`,
`ODOO_TEAM_DB_PATTERN=crm-{slug}` (per-team db routing — same idea as
`TAIGA_TEAM_PROJECT_PATTERN`). Backup of the pre-change env:
`/opt/amebo/backend/.env.bak-before-odoo-20260820`. The password is **not** in
git anywhere.

Verified: amebo's own code (`_odoo(context)`) routes org vc → `crm-vc` (275
contacts) and org integralmass → `crm-integralmass` (6) — each team gets its own
contacts, not another team's.

## 2. Taiga — DONE

Taiga user `amebo` (id 17) added as **member (role `back`) of all 6 team
boards** (was 0 memberships). Password unchanged (reused the existing
`TAIGA_PASSWORD` in amebo's env). **Superuser dropped 2026-08-20**
(`is_superuser=false`, still active) — verified amebo still lists the vc board
via membership, so board tools keep working at least privilege.

## 3. odoo-cli — INSTALLED manually (per `roles/agent-clis`)

Sparse checkout of `git@github.com:Cooperation-org/cobox.git` (`/scripts/`
only) → **`/opt/agent-clis/cobox`**, symlink **`/usr/local/bin/odoo-cli`** →
`cobox/scripts/odoo-cli.sh`. Cloned as the `amebo` user with
`/etc/earnkit/github-deploy-key`. (`mcp-taiga` was already installed at
`/opt/agent-clis/mcp-taiga`.)

Works per-team: `status`, `user-list`, `contact-list`, `contact-search`
(with `ODOO_DB=crm-<slug>`).

**FIXED 2026-08-20 (cobox `bcb49ea`):** `contact-search`/`contact-export`
hardcoded the custom field `res.partner.x_abra_catcode`, which the team CRM dbs
do not have (only `linkedtrust_crm` does) → XML-RPC fault. Now the field is
detected with `fields_get` and included only when present; linkedtrust keeps
catcode search, team dbs work. Verified: crm-vc "Greg"→3, crm-integralmass
"Baah"→its own contact. Change is in the cobox repo (pushed), and the box
checkout at `/opt/agent-clis/cobox` was reset to origin/main.

## 4. abra / knowledge — resolved 2026-08-20 (in-process path kept, external dropped)

amebo has TWO knowledge backends:

- **In-process, per-org (KEPT):** `search_knowledge_base` + `lookup_contact`
  run via `BindingService(org_id)` against amebo's OWN local `abra_*` tables in
  `amebo_vc` — no external binary, no external DB, org-isolated. Verified live
  for org 1 and 48: they execute cleanly and return "No results" only because
  no knowledge has been ingested into those local tables yet (empty, not
  broken). This is the right multi-tenant fit; ingestion into the local
  `abra_*` tables is the separate step that makes them return content.
- **External `abra` binary (`abra`, `abra_search`) — NOT wired, and removed
  from vc's allowed_tools (43→41).** The `abra` CLI
  (`Cooperation-org/abra` → `impl/abra` → `pgvector/query.py`) reads the abra
  DB on VM 100, whose tables are owned by the **`cobox`** role. There is **no
  `cobox` credential on this box** and the local admin (`odoo_vc`) is not a
  superuser, so it can neither read those tables nor grant access — I will not
  guess the password. It would also read the SHARED linkedtrust knowledge, so
  pointing every team at it breaks the per-team isolation the in-process path
  gives. Decision: drop the external abra tools from the cohort; rely on the
  in-process KB.

If a team-wide (non-isolated) abra is ever wanted here, it needs the `cobox` DB
password (lives in the dev-VM `abra/impl/.env`) set as `ABRA_DATABASE_URL`, the
abra CLI installed in its own venv (its `impl/abra` wrapper hardcodes the
dev-VM path `/opt/shared/repos/abra/impl` and would need a path fix), and
`sentence-transformers` for embedding search. Deferred on purpose.

## 5. To make this durable in earnkit (not yet done — needs VM 200 private inv)

- Add `amebo_odoo_service_password` (+ login/name, and the taiga service
  login/password/email) to the private inventory `inventory/workers-vc` on the
  repo-of-record (VM 200).
- Render them through `roles/runner/templates/inventory-group-vars.yml.j2`, and
  add `ODOO_URL` + `ODOO_TEAM_DB_PATTERN=crm-{slug}` to
  `roles/amebo/templates/amebo.env.j2`, so a future box gets all of this from a
  clean run instead of by hand.

## 6. Playbook re-stage

`/opt/earnkit/stack/playbooks` was re-synced from this checkout on 2026-08-20
(playbooks tree only) so `refresh-team.yml` + `tasks/{odoo,taiga}-service-user`
+ `tasks/amebo-instance` are present on the box.
