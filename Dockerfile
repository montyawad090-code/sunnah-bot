# Host-agnostic image (works on Render, Koyeb, Fly, a VPS, Oracle Cloud, etc.)
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY sunnah_bot.py .
# Run as an unprivileged user; /app/data holds state.json if you mount a volume
# there (set DATA_DIR=/app/data), otherwise use DATABASE_URL.
RUN useradd --create-home --uid 10001 bot && mkdir -p /app/data && chown bot /app /app/data
USER bot
# Token & settings are provided as environment variables / secrets at runtime.
CMD ["python", "-u", "sunnah_bot.py"]
