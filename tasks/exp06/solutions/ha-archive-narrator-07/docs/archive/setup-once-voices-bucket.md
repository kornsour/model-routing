# One-time setup: move voice models off the shared bucket

**Done 2026-06-20.** Voice models used to be downloaded from a shared S3
bucket on first run. They now ship as a local download script
(`python -m narrator.voices fetch`), and the bucket was emptied and deleted.

Steps that were run once:

1. Copy each `.onnx` and `.json` pair from the bucket to the release assets.
2. Point `narrator.voices.fetch` at the release assets.
3. Empty and delete the bucket.
