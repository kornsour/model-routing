# Agent and infrastructure guide

## Source of truth

This public template deliberately does not name an organization's accounts,
domains, role ARNs, state buckets, or internal documentation location. When a
project is created from the template, record its organization-level IaC source
of truth in that project's private `PROJECT_CONTEXT.md`.

This repository owns infrastructure that deploys the application built from
this template. Keep runtime resources, state backend/key, role ARN,
environments, and rollback procedure in the derived application's repository.

## Before provisioning

1. Record the AWS account, regions, environments, state backend/key, deploy
   role, data classification, budget, and rollback target in
   `PROJECT_CONTEXT.md`.
2. Use GitHub OIDC with an exact repository and protected-environment trust;
   never use long-lived AWS keys in CI or application configuration.
3. Tag resources with `Application`, `Environment`, `Owner`, `ManagedBy`, and
   `Lifecycle`.
4. Start experiments in a shared Applications or Sandbox boundary. Use a
   dedicated production account only for customer data, material blast radius,
   distinct cost/quotas, or distinct security/retention requirements.

## Public configuration and secrets

- Public docs and examples must use placeholders such as `<AWS_ACCOUNT_ID>`,
  `<AWS_REGION>`, `<DEPLOY_ROLE_ARN>`, and `<STATE_KEY>`; never replace them
  with organization-specific values.
- Keep non-secret deployment configuration in the protected deployment
  environment's configuration variables. Keep credentials, database URLs,
  signing keys, and third-party tokens in that environment's encrypted secrets.
- GitHub Actions deployments must use OIDC, not `AWS_ACCESS_KEY_ID` or
  `AWS_SECRET_ACCESS_KEY`. If an externally hosted runtime must call AWS
  directly, use a narrowly scoped, rotatable credential stored only as a runtime
  secret, never in source, examples, GitHub Actions, or a public document.
- Document secret *names* and required scopes, never their values.

## Delivery rules

- Place OpenTofu or other deployable IaC under `infra/` in the derived app.
- Pull requests must include the relevant plan plus cost, secret-name-only,
  migration, and rollback notes.
- Apply only from a protected deployment environment after review, then verify
  the resulting live state.
- Do not create accounts, DNS records, paid resources, production data changes,
  or public endpoints without explicit user authority.
- Prefer pay-per-use services; treat persistent databases, NAT gateways, public
  IPs, provisioned concurrency, and unbounded logs as explicit cost decisions.
