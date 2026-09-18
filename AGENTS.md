# Agent instructions

Read [`CLAUDE.md`](./CLAUDE.md) and [`docs/agent.md`](./docs/agent.md) before
changing this template or provisioning cloud resources.

- Run `make check` before publishing changes.
- Keep deployable application infrastructure in this repository once it exists.
- The organization-level source of truth is named only in the derived project's
  private `PROJECT_CONTEXT.md`; do not expose it in this public template.
- Use GitHub OIDC, never long-lived cloud credentials. Do not create accounts,
  DNS/public endpoints, billable resources, or production changes without
  explicit authority.
- [`archive/`](./archive/) holds historical/superseded documentation and
  records only. Do not treat anything under it as current state or use it to
  inform new work.
