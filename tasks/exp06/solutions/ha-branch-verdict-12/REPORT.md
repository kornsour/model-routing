# folio-site `feat/aws-static-site`

VERDICT: NEEDS-DECISION

- Squash check: `+`, never merged. One commit, 27 behind main.
- `git diff --shortstat main..feat/aws-static-site`: 31 files changed, 64 insertions(+), 159 deletions(-). Merging would revert main's projects, blog and Pages work.
- Absent from main, infra: `infra/s3-site.tf`, `.github/workflows/aws-static-site.yml`.
- Absent from main, application/content: `site/contact.html`, `site/js/contact-form.js` (a working contact form; open issue #7 asks for exactly this).
- Main deploys with GitHub Pages (`.github/workflows/pages.yml`), which supersedes the S3/CloudFront approach. No PR exists.

The hosting half is superseded and should not land, but the contact page is unique work that issue #7 still wants. Do not delete and do not PR as-is: port the two contact files onto current main in a fresh branch, then delete this one.

```json
{"verdict": "NEEDS-DECISION", "absent_from_main": {"infra": ["infra/s3-site.tf", ".github/workflows/aws-static-site.yml"], "application": ["site/contact.html", "site/js/contact-form.js"]}, "behind": 27}
```
