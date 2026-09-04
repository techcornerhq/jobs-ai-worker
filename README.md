# Jordan Jobs AI Worker

Public zero-paid-AI worker for **وظائف الأردن - فرص عمل يومية**.

This repository intentionally contains **no Blogger/Google secrets**. It discovers a public job candidate, resolves public source details, runs **Qwen3-8B locally on the GitHub-hosted runner via llama.cpp**, applies cross-source campaign/repost deduplication, and produces a structured publication package for the private publisher repository.

## Zero-cost rule

- No OpenAI / Anthropic / Gemini / Groq / paid inference APIs.
- No API token billing.
- AI provider must be `local_qwen_llama_cpp` and `paid_api_used` must be `false`.
- If local Qwen fails, the workflow fails instead of silently using a paid fallback.

## Data flow

`public sources -> discovery -> source resolution -> Qwen enrichment -> campaign/repost dedupe -> Blogger-ready HTML/JSON output`

The private `techcornerhq/jobs` repository remains responsible for Blogger OAuth and publication.

## First test

Run **Qwen Job Worker** manually from Actions with `candidate_index=0`. The workflow is dry-run only and will commit `data/results/latest.json` when successful.
