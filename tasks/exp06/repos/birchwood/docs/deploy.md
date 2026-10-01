# Deploying birchwood

1. Merge to `main`; CI builds the wheel.
2. `make release` tags the commit and uploads the wheel.
3. On the VM: `sudo systemctl restart birchwood` picks up the new wheel.

Database migrations run on start (`birchwood migrate` is idempotent).
