# Dark Pattern Auditor — production image.
# Built on Playwright's official image, so headless Chromium and all the OS
# libraries it needs are already installed. Works on Render, Hugging Face
# Spaces, Fly.io, Google Cloud Run, or any Docker host.
FROM mcr.microsoft.com/playwright/python:v1.60.0-jammy

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DPA_HOST=0.0.0.0

WORKDIR /app

# Install Python dependencies first for better layer caching.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Make sure the Chromium build matches the installed Playwright exactly.
RUN python -m playwright install chromium

# Copy and install the application.
COPY pyproject.toml README.md ./
COPY src ./src
COPY web ./web
RUN pip install --no-cache-dir -e .

# Listens on $PORT when the platform provides one (Render, Cloud Run), else 7860
# (Hugging Face Spaces' default app_port). Override with -p / env as needed.
EXPOSE 7860
CMD ["sh", "-c", "uvicorn dpa.server:app --host 0.0.0.0 --port ${PORT:-7860}"]
