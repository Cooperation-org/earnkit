# earnkit

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
  or manual dispatch. Third-party tools (Taiga, Odoo) update via playbook re-run.
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
#    gets an internal, LinkedTrust-linked user in the team CRM and a membership
#    in the team's Taiga project. Idempotent — run after add-team and again
#    whenever membership changes:
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
site.yml                  # the full-stack playbook (tags: base,rabbitmq,taiga,marten,odoo,amebo,govkit,workersvc,cicd,nginx)
playbooks/add-team.yml    # per-team provisioning (team-level resources ONLY, never individual users)
playbooks/sync-team-members.yml  # reconcile GovKit members -> team CRM users + Taiga memberships
playbooks/upgrade-crm-addons.yml # odoo-bin -u for the custom addons across every team database
roles/                    # one role per concern; no app code
inventory/example/        # documented sample inventory — copy it out, never commit real values
cicd/workflow-samples/    # GitHub Actions deploy workflows to drop into tool repos
docs/DECISIONS.md         # the settled design decisions and their reasons
```
