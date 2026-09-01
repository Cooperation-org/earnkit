# earnkit

> ## ⛔ DO NOT REDEPLOY FROM EARNKIT — EVER
>
> **The current workers.vc VM (517, 10.0.0.17) is NOW ON MANUAL MODE.** (2026-08-26)
> The playbooks below were used for initial setup only. All changes to the VM are made
> manually on the VM; this repo is updated afterward as the record. Do not run ansible
> against it.
>
> **earnkit (`/home/golda/earnkit`, `/opt/earnkit/stack`) is REFERENCE ONLY.**
> Re-running earnkit (`ansible-playbook site.yml` or any play) **re-templates and
> OVERWRITES each app's `.env`**, silently dropping hand-added vars (ODOO / TAIGA /
> goal-scheduler / S2S / Discord). This gutted amebo's live config on **2026-08-24**.
> Use earnkit only to *read* how something was first wired.
>
> **Runtime config lives in ONE hand-maintained `.env` per app — edit it directly, never regenerate:**
> - amebo → `/opt/amebo/backend/.env`  (read by systemd `EnvironmentFile=` **and** the app's `load_dotenv()`)
> - govkit → `/opt/govkit/src/.env`  ·  workersvc → `/opt/workersvc/src/.env`
>
> There is **no** central/secret `.env` and **no** generator. New env var? Add it to that
> app's `.env`, **by hand**, in that one place.

> ## 📖 Infra / TLS / subdomains / edge routing → read the **cobox** repo FIRST
>
> Our edge/TLS/subdomain layout is **not** what you expect and people keep breaking it by
> assuming a normal certbot/wildcard/reverse-proxy setup. Before changing nginx, a domain,
> a cert, or deploying a new hostname, read the private **cobox** repo
> (`github.com/Cooperation-org/cobox` — deployers have access):
> `README.md`, `app-registry.md`, `app-vm-best-practices.md`, `setup-new-app-vm.md`.
> TLS terminates at the edge, **not** on the app VM; app VMs run nginx on **port 80 only**;
> there is **no** wildcard cert and **no** certbot. Don't guess the routing — look it up there.

**One Ansible playbook that stands up the earned-governance stack on a fresh VM.**

earnkit composes tools that each work on their own — it contains no application
code, only automation that installs each tool from its own repository and wires
them together:

| Tool | Repo | What it does |
|---|---|---|
| **GovKit** | `Cooperation-org/govkit` | earned governance: task→equity drops, the pie, votes, sortition |
| **Taiga** | upstream + `Cooperation-org/taiga-contrib-linkedtrust-auth` | task tracker (the source of earned value) |
| **Marten** | `Cooperation-org/marten` | modern frontend for Taiga |
| **Odoo 17** | upstream (source install) | CRM |
| **amebo** | `Cooperation-org/amebo` | the team's knowledge-cooperation agent |
| **workersvc** | `Cooperation-org/workers.vc` | Workers.vc public face: VC landing, accelerator pages, invite doorway |

How those tools compose into one dashboard page — the component contracts, the
catalog, and how to run the set on a laptop — is documented once, in
**`govkit/docs/COMPOSITION.md`**. earnkit provisions the hosts; that document
explains what runs on them.

Design rules (settled — see `docs/DECISIONS.md`):

- **No Docker, no containers.** Everything runs native under systemd.
- **No local Postgres.** All databases live on an external Postgres you point at
  with `database_host`. The VM holds code, config, and RabbitMQ only — it is
  nearly stateless and cheap to rebuild from this playbook.
- **LinkedTrust SSO everywhere.** Every service logs in against a LinkedTrust
  OIDC provider (`oidc_issuer`). The IdP is NOT on this VM.
- **Multitenant for a cohort** (10–12 teams on one VM): amebo instances,
  GovKit orgs, one private Taiga project per team, one Odoo database per team
  (dbfilter by hostname). `playbooks/add-team.yml` provisions a team.
- **Each tool remains independently useful.** earnkit never forks or patches a
  tool; anything a tool needs to support composition belongs in that tool's repo.
- **CI/CD per tool.** The playbook provisions a restricted `deploy` user and
  per-tool update scripts; each of our tool repos adds a small GitHub Actions
  workflow (samples in `cicd/workflow-samples/`) that deploys on merge to main
  or manual dispatch. The custom Odoo addons deploy the same way: their
  workflow calls `update-crm-addons`, which refreshes every addon checkout and
  runs `odoo-bin -u` against every team database. Odoo and Taiga themselves
  update via playbook re-run.
- **No secrets in git.** `inventory/example/` carries sample values only; your
  real inventory lives outside the repo or in Ansible Vault.

## Quick start

```bash
# 0) prerequisites on your workstation
pip install ansible-core
ansible-galaxy collection install -r requirements.yml

# 1) copy the example inventory somewhere PRIVATE and fill it in
cp -r inventory/example /path/to/private/inventory
$EDITOR /path/to/private/inventory/group_vars/all.yml

# 2) a fresh Ubuntu 24.04 VM you can ssh into as root or a sudoer
#    (you create the VM; the playbook only targets a hostname)

# 3) run it
ansible-playbook -i /path/to/private/inventory/hosts.yml site.yml

# 4) add a team
ansible-playbook -i /path/to/private/inventory/hosts.yml playbooks/add-team.yml \
  -e team_slug=sunrise -e team_name="Sunrise Co-op"

# 5) once invites are accepted, sync members: every GovKit member of each team
#    gets an internal, LinkedTrust-linked user in the team CRM (needs their
#    LinkedTrust sub, i.e. one GovKit login) and an email-matched user +
#    membership in the team's Taiga project. Idempotent — run after add-team
#    and again whenever membership changes.
#    CAVEAT: Taiga login matches by email only, so a member whose GovKit email
#    differs from their LinkedTrust email gets a DUPLICATE Taiga user at first
#    login — keep the two emails aligned.
ansible-playbook -i /path/to/private/inventory/hosts.yml playbooks/sync-team-members.yml
```

Then route hostnames to the VM (reverse proxy / DNS is site-specific; each
service's port is a variable — see `inventory/example/group_vars/all.yml`).

## What the operator still does by hand

- Create the VM and DNS/proxy routes.
- Register one OIDC client per service on the LinkedTrust IdP and put the
  credentials in your inventory (vault).
- Add the deploy key + workflow file to each tool repo you want CI/CD for.
- Slack app credentials for amebo (if using Slack).
- Re-run `playbooks/sync-team-members.yml` when team membership changes
  (member orchestration ultimately belongs to amebo — DECISIONS.md #6; this
  playbook is the operator-run reconcile until amebo covers CRM + Taiga).

## Layout

```
site.yml                  # the full-stack playbook (tags: base,rabbitmq,taiga,marten,odoo,amebo,agent-clis,govkit,workersvc,cicd,nginx)
playbooks/add-team.yml    # per-team provisioning (team-level resources ONLY, never individual users)
playbooks/refresh-team.yml # give an EXISTING team what add-team has learned since (never touches its database)
playbooks/sync-team-members.yml  # reconcile GovKit members -> team CRM users + Taiga memberships
playbooks/upgrade-crm-addons.yml # odoo-bin -u for the custom addons across every team database
                          #   (the same work an addon repo's push triggers via /opt/earnkit/bin/update-crm-addons)
roles/                    # one role per concern; no app code
inventory/example/        # documented sample inventory — copy it out, never commit real values
cicd/workflow-samples/    # GitHub Actions deploy workflows to drop into tool repos
docs/DECISIONS.md         # the settled design decisions and their reasons
```
