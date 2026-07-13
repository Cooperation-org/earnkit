# SSO, team membership, and invites — the design

*2026-07-13. Everything below was verified against the actual code of the IdP
(trust_claim_backend), GovKit, the Taiga auth plugin, stock Odoo auth_oauth,
and the live CRM's provider configuration — file/line references in the
research notes. Nothing here is speculative except where marked "to build".*

## 1. One identity: LinkedTrust OIDC

Every service in the kit authenticates against the LinkedTrust OIDC provider
(`oidc_issuer`). The stable identity is the OIDC **`sub`** claim. A person on
three teams has ONE login for every tool.

Verified today:
- The IdP is a full OIDC provider (authorize/token/userinfo, JWKS, discovery).
- Endpoints confirmed from the live CRM's working provider row:
  `/oauth/authorize`, `/oauth/userinfo`, scope `openid email trust`.
- GovKit maps `sub` → local user (primary key match), auto-creates on first
  login, links by verified email with an anti-takeover guard.
- Odoo stock `auth_oauth` maps `sub` → `oauth_uid` per database.
- The Taiga plugin (back half) does find-or-create from the LinkedTrust
  identity; its login button belongs in the frontend (Marten).

## 2. Team membership: attestations are the source of truth

A membership is a LinkedTrust claim:

```
<person-uri>  MEMBER_OF  <team-uri>     aspect: admin|steward|member
```

issued through an authenticated flow (howKnown: VERIFIED_LOGIN), revoked by a
counter-claim. Local membership tables in each tool become **materializations**
of these attestations, synced at login — never hand-maintained per tool.

**The delivery mechanism already exists as a designed seam.** The IdP's `trust`
scope is granted by default to every kit client, and its payload comes from
`resolveTrustSignal(userId)` — which is today an explicit stub ("real
implementation will resolve vouches / roots-of-trust from the Claim graph").
GovKit even requests the `trust` scope already but never reads it.

**To build (the critical path, in order):**
1. **IdP**: implement `resolveTrustSignal` to include
   `teams: [{slug, role, claim_id}]` from MEMBER_OF claims over the user's
   identity closure. Small, testable on dev.linkedtrust.us.
2. **GovKit**: at OIDC login, sync `trust.teams` → `Membership` rows
   (get_or_create per org, role-mapped; setting-gated). Fits its existing
   "explicit, never inferred" principle — an attestation IS explicit.
3. **Taiga plugin**: same sync → project memberships (project slug = team slug).
4. **Odoo**: no claim support in stock auth_oauth (verified). Interim: amebo
   provisions the user row in the team DB via XML-RPC when membership is
   granted; the person's SSO login then just works. A custom module reading
   `trust.teams` is the later replacement (known-prerequisite work, unchanged
   from the 7/6 spec).
5. **amebo**: already has per-org membership tables (org_member,
   person_identity) — sync from the same signal, or more likely amebo is the
   *issuer* of MEMBER_OF claims as the people-orchestrator.

## 3. Invite links

**What exists today (verified):**
- **GovKit has a complete, correct invite mechanism**: an org admin mints a
  *stateless signed token link* (14-day expiry, role + org baked in, no DB
  row, idempotent acceptance). Crucially it **already composes with SSO**: an
  anonymous invitee's token is stashed in session, they log in with
  LinkedTrust, and the membership materializes post-login.
- The LinkedTrust frontend has NO invite mechanism (its "endorse" links are
  claim-id URLs, not invites). The IdP has none either.

**Kit v1 (works the day the VM exists, zero new code):** GovKit's invite link
is *the* team invite. Flow: team admin (or Golda) mints link in GovKit →
invitee clicks → "Continue with LinkedTrust" (signup if new) → GovKit
membership exists. Taiga/Odoo/amebo access is then provisioned by amebo
("add <person> to team <team>" — gated) or by an operator, until §2 sync lands.

**Target (v2): invites live at the IdP** so one link grants the whole kit:
`POST /oauth/invites` (client-credentialed, team + role + expiry) → invitee
opens `join/<token>` → authenticates → **IdP issues the MEMBER_OF claim** →
redirect to the team's home. Every tool then picks the membership up from
`trust.teams` at next login. This replaces nothing — GovKit's mechanism simply
becomes a client of it. (This is the "issue-claim/invite endpoint" flagged as
prerequisite work in the 7/6 spec.)

## 4. Multitenancy: the honest per-tool verdict

One VM, 10–12 teams, people on multiple teams:

| Tool | Really multitenant? | Kit approach | Multi-team person | Sharp edges |
|---|---|---|---|---|
| **GovKit** | **Yes** (native orgs) | one process | native — one user, N memberships, org picker at `/` | scoping is call-site discipline (`.for_org()`), not DB-enforced; fine at cohort scale, audit before strangers share it |
| **Taiga** | **No** — and that's OK | ONE instance, one **private project per team** | native — one user, N project memberships | instance-wide user search can expose usernames across teams; `/media` URLs unguessable but unprotected |
| **Odoo** | **No** (single-DB multi-company is the wrong tool here) | **one database per team**, dbfilter by hostname | same SSO identity; a user row per team DB | stock auth_oauth only links *existing* users → each membership needs a provisioning step (amebo, §2.4); websockets need a `/websocket` route to gevent port if live-chat is wanted |
| **amebo** | **Yes** (instances + July multi-org core) | one process, an instance row per team | native (person_identity + org_member; §4.2 resolution) | ⚠ **HARD BLOCKER, already on the amebo board**: the `LEGACY_ENV_ORG_ID` unscoped fallback must be fixed **before a second org exists**, or cross-tenant misroute is possible. The cohort is 10+ orgs — this fix is a launch gate. |

Conclusion: Golda's instinct is right — Odoo and Taiga aren't multitenant, and
the kit doesn't pretend they are. DB-per-team and project-per-team are the
correct shapes at this scale, with SSO making the seams invisible to people.

## 5. The initial team (demo bootstrap)

1. Provision the VM: `ansible-playbook site.yml`.
2. Create the first team: `ansible-playbook playbooks/add-team.yml -e
   team_slug=cohort0 -e team_name="Cohort Zero"` (Odoo DB with the CRM addons
   + LinkedTrust provider registered, Taiga private project, amebo instance,
   GovKit org + ValuationConfig).
3. Bootstrap the first admin (one-time, until IdP invites exist): GovKit's
   `seed_org`-style path — create the operator's membership as admin in the
   new org (management shell; the operator logs in via LinkedTrust first so
   the user row exists, then is promoted). Taiga superuser comes from the
   taiga role; Odoo team-DB admin from the DB init.
4. The admin mints GovKit invite links for the first members → they join via
   LinkedTrust SSO. That is the demo: **invite link → SSO → you're on the
   team → your work shows in Taiga/Marten → your equity shows in GovKit.**
5. Dogfood candidate for team zero: LinkedTrust itself.

## 6. Local CRM modifications (captured 2026-07-13)

The live CRM's local value, now flowing into the kit:
- `crm_card_scanner`, `crm_outreach_runner` — in git; **wired into the kit**
  (`odoo_custom_addons` + installed into every team DB via
  `odoo_team_init_modules`).
- `crm_relationship_dashboard` ("per-owner relationship view: last message,
  next follow-up, overdue") and `quick_outreach` ("paste LinkedIn message,
  create outreach lead instantly") — **exist ONLY on the live VM, no git**.
  They need repos before the kit can carry them (one `git init` + push each;
  flagged to Golda).
- `configure-odoo.py` (adds `x_abra_catcode` field + private-contact record
  rules via XML-RPC) — should become a post-init step in `add-team.yml` so
  every team DB gets the same shape. To wire once its home repo is decided.
- The live provider row also confirmed the real OIDC endpoints and the `trust`
  scope (already folded into add-team.yml).
