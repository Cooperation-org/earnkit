# earnkit — settled decisions

Origin: Golda's design sessions 2026-07-06 (cohort-VM Ansible spec) and
2026-07-12 (this repo). These are settled; changes go to Golda.

1. **Own repo.** earnkit composes; it holds no app code. Each tool (GovKit,
   amebo, Marten, Taiga, Odoo) works standalone; anything a tool needs for
   composition belongs in the tool's own repo. (2026-07-12 — supersedes the
   7/6 note that placed the playbook in govkit/deploy/.)
2. **No Docker/Compose/containers.** Native systemd services only.
3. **No local Postgres.** All DBs on `database_host` (ours: the VM 100
   cluster). The cohort VM holds code, config, RabbitMQ — nearly stateless,
   rebuildable from the playbook.
4. **LinkedTrust OIDC SSO** default login for every service; IdP off-VM.
5. **Multitenancy per service**: amebo instances, GovKit orgs, one Taiga
   project per team, one Odoo DB per team (dbfilter). `add-team.yml`
   provisions TEAM-level resources only — people are amebo's job.
6. **Amebo orchestrates people; Ansible provisions services.** "Add a member"
   is an amebo capability (IdP claims + per-service APIs), not a playbook step.
7. **CI/CD**: merge to main in a tool repo (or manual dispatch) → GitHub
   Action sshes as the restricted `deploy` user and runs that tool's
   whitelisted update script. Taiga/Odoo (third-party) update by playbook
   re-run instead.
8. **No secrets in git**, sample inventory only; real inventory lives outside
   the repo (vault for secrets). No person names in committed files.

Open questions for Golda (from the 7/6 spec, still open):
- Where the real inventory lives (private repo vs local file).
- Cohort VM number/name/RAM when she creates it (500+, ~8GB/4c start).
- ~~Hostname scheme~~ DECIDED 2026-07-13 (rev 2, Golda + two sessions concur):
  **the member chain lives on workers.vc** — invite doorways at
  workers.vc/i/<code>, dashboard dash.workers.vc, taiga./martin./amebo./
  crm-<team>.workers.vc (wildcard DNS -> host). Brand roles (rev 3): workers.vc = THE ACCELERATOR,
  whole public surface + member chain (landing, wall, opportunities, invites,
  dashboard); cooperation.org = movement umbrella; linkedtrust.us = the founding
  entity's own site + the rails (SSO, attestations); earnedgov.com = redirect. Claims' effort URI stays
  linkedtrust.us/earnedgov (immutable history); wall code already accepts
  multiple effort URIs. Odoo IdP client gains one redirect URI per team at
  add-team time.
- Slack app registration per-team vs one app (affects amebo config).
- Confirm Odoo one-DB-per-team over multi-company (spec leans per-team DB).
- Taiga OIDC redirect URI: the LinkedTrust plugin ships back-half only; the
  login button lives in the frontend — likely Marten. Default is the taiga
  domain; probably wants https://<marten_domain>/oauth/callback. Confirm.
- Taiga /media is served without access control (classic native install;
  URLs unguessable). Revisit if cohort privacy requires the protected
  storage service.
