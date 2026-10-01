# Release plan v2

Releases are tagged from `main` by `make release`; CI builds and uploads the
wheel, and the VM pulls the tagged wheel on restart. See `deploy.md` for the
operator steps.
