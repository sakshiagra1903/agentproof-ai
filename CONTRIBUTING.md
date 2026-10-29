# Contributing

1. Open an issue describing the bug or proposed metric.
2. Create a focused branch and keep changes small.
3. Add deterministic tests for new behavior; do not call live LLM APIs in tests.
4. Run `python -m pytest -q` and the CLI gate before submitting.
5. Document assumptions and limitations, especially for evaluation metrics.
6. Never include secrets, real customer conversations, or proprietary datasets.

By submitting a contribution, you agree that it may be distributed under the project's MIT license.
