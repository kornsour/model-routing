#!/usr/bin/env bash
# Builds folio-site's history for ha-branch-verdict-12: feat/aws-static-site is
# one commit (S3/CloudFront infra plus a contact page and its script) off an
# old main; main has moved 27 commits on and deploys with GitHub Pages.
set -euo pipefail
# The sandbox's first commit carries today's date; back-date it so the history
# below is never older than its own root (clock skew breaks `git rev-list A..B`).
GIT_COMMITTER_DATE="2026-07-01T09:00:00Z" git -c user.name=sandbox -c user.email=sandbox@local \
  commit -q --amend --no-edit --date="2026-07-01T09:00:00Z"
export GIT_AUTHOR_NAME="Folio Owner" GIT_AUTHOR_EMAIL="owner@folio.example"
export GIT_COMMITTER_NAME="Folio Owner" GIT_COMMITTER_EMAIL="owner@folio.example"
n=0
commit() {
  n=$((n + 1))
  GIT_AUTHOR_DATE="$(date -u -j -v+"${n}"H -f %Y-%m-%dT%H:%M:%SZ 2026-09-01T08:00:00Z +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -d "2026-09-01T08:00:00Z + ${n} hours" +%Y-%m-%dT%H:%M:%SZ)"
  export GIT_AUTHOR_DATE GIT_COMMITTER_DATE="$GIT_AUTHOR_DATE"
  git add -A && git commit -q -m "$1"
}
git branch -M main

git switch -q -c feat/aws-static-site
mkdir -p infra .github/workflows site/js
cat > infra/s3-site.tf <<'EOF'
resource "aws_s3_bucket" "site" {
  bucket = "folio-site-static"
}

resource "aws_cloudfront_distribution" "site" {
  enabled             = true
  default_root_object = "index.html"
  origin {
    domain_name = aws_s3_bucket.site.bucket_regional_domain_name
    origin_id   = "site"
  }
  default_cache_behavior {
    target_origin_id       = "site"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
  }
  restrictions {
    geo_restriction { restriction_type = "none" }
  }
  viewer_certificate { cloudfront_default_certificate = true }
}
EOF
cat > .github/workflows/aws-static-site.yml <<'EOF'
name: AWS static site
on:
  push:
    branches: [feat/aws-static-site]
permissions:
  contents: read
  id-token: write
jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@08eba0b27e820071cde6df949e0beb9ba4906955 # v4.3.0
      - run: aws s3 sync site s3://folio-site-static --delete
EOF
cat > site/contact.html <<'EOF'
<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Contact</title><link rel="stylesheet" href="css/style.css"></head>
<body><main><h1>Contact</h1>
<form id="contact" novalidate>
  <label>Name <input name="name" required></label>
  <label>Email <input name="email" type="email" required></label>
  <label>Message <textarea name="message" required></textarea></label>
  <button>Send</button>
  <p id="status" role="status"></p>
</form>
<script src="js/contact-form.js"></script></main></body></html>
EOF
cat > site/js/contact-form.js <<'EOF'
// Validates the contact form client-side and posts it to the form endpoint.
const form = document.getElementById("contact");
const status = document.getElementById("status");
const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(form));
  if (!data.name || !EMAIL.test(data.email) || data.message.length < 10) {
    status.textContent = "Please fill in every field (message at least 10 characters).";
    return;
  }
  const res = await fetch("https://forms.folio.example/contact", { method: "POST", body: JSON.stringify(data) });
  status.textContent = res.ok ? "Thanks, I'll reply within a few days." : "Something went wrong; email me instead.";
});
EOF
commit "feat: host on S3 + CloudFront, add contact page"

git switch -q main
mkdir -p site/projects site/blog .github/workflows
cat > .github/workflows/pages.yml <<'EOF'
name: Pages
on:
  push:
    branches: [main]
permissions:
  contents: read
  pages: write
  id-token: write
jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: github-pages
    steps:
      - uses: actions/checkout@08eba0b27e820071cde6df949e0beb9ba4906955 # v4.3.0
      - uses: actions/upload-pages-artifact@56afc609e74202658d3ffba0e8f6dda462b719fa # v3.0.1
        with: { path: site }
      - uses: actions/deploy-pages@d6db90164ac5ed86f2b6aed7e0febac5b3c0c03e # v4.0.5
EOF
commit "ci: deploy with GitHub Pages"
for i in $(seq 1 12); do
  cat > "site/projects/project-${i}.html" <<EOF
<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Project ${i}</title><link rel="stylesheet" href="../css/style.css"></head>
<body><main><h1>Project ${i}</h1>
<p>What it was, what I did, and what changed because of it. Project ${i} moved a team's
deploys from a wiki page of manual steps to a pipeline anyone could read.</p>
<p>Stack: Python, Terraform, GitHub Actions. Outcome: lead time down, pages down.</p>
</main></body></html>
EOF
  commit "content: project ${i} write-up"
done
for i in $(seq 1 10); do
  cat > "site/blog/post-${i}.html" <<EOF
<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Post ${i}</title><link rel="stylesheet" href="../css/style.css"></head>
<body><main><article><h1>Notes ${i}</h1>
<p>A short note on platform work: paved roads, golden paths and the places they
stop. Part ${i} of an occasional series.</p></article></main></body></html>
EOF
  commit "blog: notes ${i}"
done
cat >> site/css/style.css <<'EOF'
main h1 { font-size: 2rem; }
article p { line-height: 1.6; }
EOF
commit "style: typography for long pages"
cat > site/index.html <<'EOF'
<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Folio</title><link rel="stylesheet" href="css/style.css"></head>
<body><header><a href="index.html">Home</a> <a href="about.html">About</a> <a href="projects/project-1.html">Projects</a> <a href="blog/post-1.html">Blog</a></header>
<main><h1>Hi, I build developer platforms.</h1><p>Projects and notes below.</p></main></body></html>
EOF
commit "nav: link projects and blog"
cat > site/404.html <<'EOF'
<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Not found</title></head><body><p>Not found. <a href="index.html">Home</a></p></body></html>
EOF
commit "feat: 404 page for Pages"
cat > site/about.html <<'EOF'
<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>About</title><link rel="stylesheet" href="css/style.css"></head>
<body><main><h1>About</h1><p>Platform engineer. I like boring infrastructure, fast feedback
and docs that tell you what to do next. Currently leading a developer-experience team.</p></main></body></html>
EOF
commit "content: refresh about page"

origin="$(pwd)/.git/fixture-origin.git"
git clone -q --bare . "$origin"
git remote add origin "$origin"
git fetch -q origin
git branch -q --set-upstream-to=origin/main main
git switch -q main
