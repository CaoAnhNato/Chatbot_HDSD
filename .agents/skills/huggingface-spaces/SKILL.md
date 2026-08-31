---
name: huggingface-spaces
description: Build, deploy, and maintain applications on Hugging Face Spaces — Gradio / Docker / Static SDKs, ZeroGPU and dedicated hardware, model loading, debugging, buckets, inference providers, community grants. Use whenever the user asks to create or host an app on Hugging Face, port code onto ZeroGPU, fix a Space that won't build or run, or otherwise work with `hf spaces …`, `@spaces.GPU`, Space README frontmatter, or the `spaces` Python package.
---

# Hugging Face Spaces

Hugging Face Spaces host machine-learning applications. There are 1M+ today; each Space is a git repo. This skill covers creating, building, debugging, and maintaining them.

## 0. Getting ready

Before anything else:

1. Check the `hf` CLI is installed: `which hf`. If not, `pip install -U huggingface_hub`.
2. Check the user is logged in: `hf auth whoami`. If not, run `hf auth login` — it prints a URL and a one-time code; ask the user to open the URL and enter the code, then login completes automatically (OAuth, no token needed). Alternatively, pass a write-scoped token from https://huggingface.co/settings/tokens with `--token`.
3. Note `whoami`'s `canPay` and `isPro` flags — they gate hardware choices below. A free (`isPro=False`) account can only host Static Spaces and up to 2 ZeroGPU Spaces.

## 1. What a Space is

A Space is a git repo with three possible SDKs:

- **Gradio** — most Spaces. Python, fast iteration, supports ZeroGPU.
- **Docker** — arbitrary container. Use when you need a non-Python stack or a pre-built template.
- **Static** — plain HTML, or a React/Svelte/Vue project built at deploy time.

### Hardware tiers

**ZeroGPU (`zero-a10g`)** — dynamic, per-request GPU allocation on NVIDIA RTX PRO 6000 Blackwell. Free personal accounts in good standing can host up to 2 ZeroGPU Spaces.

## 2. Create the Space

```bash
hf repos create <namespace>/<name> --type space --space-sdk gradio --flavor zero-a10g --public --exist-ok
```

## 3. Build the app

Push `app.py`, `requirements.txt`, and `README.md` to the Space repo.
