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
- Hostname scheme (affects Odoo dbfilter and OIDC redirect URIs).
- Slack app registration per-team vs one app (affects amebo config).
- Confirm Odoo one-DB-per-team over multi-company (spec leans per-team DB).
