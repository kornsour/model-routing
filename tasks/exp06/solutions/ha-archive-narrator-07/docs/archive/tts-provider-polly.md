# TTS provider: Amazon Polly

> **Deprecated.** narrator moved to local Piper TTS in 2026-06 (see `tts.md`).
> The Polly provider was removed in 0.9.0. This page describes the old setup.

Set `AWS_PROFILE=narrator` and pick a neural voice with `--polly-voice`.
Requests were batched at 2,900 characters to stay under the API limit.
