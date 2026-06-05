# Deploying Dark Pattern Auditor to the public internet

The app ships a `Dockerfile` built on Playwright's official image, so headless
Chromium "just works" on any Docker host. Two free, no-credit-card paths are
documented below.

> **You need:** your free Gemini API key (from <https://aistudio.google.com>).
> Never commit it — every option below sets it as a platform **secret**.

| | Hugging Face Spaces | Render |
|---|---|---|
| Cost | Free | Free |
| Credit card | No | No |
| RAM | High (full browser-render + **vision** works) | ~512 MB (browser may fall back to static fetch) |
| Auto-deploy from GitHub | No (push to the Space) | **Yes** (redeploys on every `git push`) |
| URL | `https://<user>-<space>.hf.space` | `https://<name>.onrender.com` |
| Best for | The most capable free demo | Least-effort, GitHub-native |

---

## Option A — Hugging Face Spaces (recommended: full vision)

1. **Sign in** at <https://huggingface.co> (you can use your GitHub account).
2. **Create a Space:** <https://huggingface.co/new-space>
   - **Space SDK:** `Docker` → **Blank** template
   - **Hardware:** `CPU basic` (free) · **Visibility:** Public
   - Name it e.g. `dark-pattern-auditor`. HF creates a repo with a starter
     `README.md` (which contains the required `sdk: docker` / `app_port: 7860`
     metadata — keep it).
3. **Add a secret:** Space → **Settings** → *Variables and secrets* →
   **New secret** → `GEMINI_API_KEY` = your key.
   (Optional *variables*: `GEMINI_MODEL=gemini-2.5-flash`, `DPA_ENGINE=auto`.)
4. **Push the app into the Space** (PowerShell, from the folder above the project):
   ```powershell
   git clone https://huggingface.co/spaces/<HF_USER>/dark-pattern-auditor hf-space
   Copy-Item "Dark Pattern Auditor\Dockerfile","Dark Pattern Auditor\requirements.txt","Dark Pattern Auditor\pyproject.toml" hf-space\
   Copy-Item -Recurse "Dark Pattern Auditor\src","Dark Pattern Auditor\web" hf-space\
   cd hf-space
   git add .
   git commit -m "Add Dark Pattern Auditor app"
   git push
   ```
   When prompted, the **username** is your HF username and the **password** is a
   HF **access token** with *write* scope (create one at
   <https://huggingface.co/settings/tokens>).
5. The Space builds the image (a few minutes) and goes live at
   **`https://<HF_USER>-dark-pattern-auditor.hf.space`**.

---

## Option B — Render (recommended: easiest, GitHub-native)

1. **Sign in** at <https://render.com> with your GitHub account.
2. **New +** → **Blueprint** → select your `Dark-Pattern-Auditor` repo.
   Render reads [`render.yaml`](render.yaml) and configures a free Docker web service.
   (Or: **New + → Web Service → Docker**, pointing at the repo.)
3. When prompted for the **`GEMINI_API_KEY`** env var, paste your key (it's marked
   `sync: false`, so it stays a secret and is never stored in the repo).
4. Click **Create** / **Deploy**. First build takes a few minutes; afterwards it
   **auto-redeploys every time you push to `main`**.
5. Live at **`https://dark-pattern-auditor.onrender.com`** (name may vary).

> Free Render services **sleep after ~15 min idle** (first request then takes
> ~30–60 s to wake) and have limited RAM. If Chromium can't start, the auditor
> automatically falls back to a fast static fetch — the AI (Gemini, text-only)
> still runs; you just lose screenshot/vision on that tier.

---

## After it's live

- Open the URL — the engine pill should read **"AI · Gemini"**.
- The public API is SSRF-guarded: it refuses to audit `localhost`/private/internal
  addresses (`DPA_ALLOW_PRIVATE_HOSTS=false` by default).
- **Cost control:** the free Gemini tier is rate-limited, which naturally caps
  abuse. For heavier use, add a real rate-limiter or put it behind auth.
- **Rotate** the key from Google AI Studio anytime; just update the platform secret.
