# Text-to-speech engine

narrator uses Piper, run locally, since 2026-06. Voices are ONNX models under
`~/.local/share/narrator/voices/`; `--voice <name>` picks one. The engine is
behind `narrator.tts.Engine` so tests use a silent fake.
