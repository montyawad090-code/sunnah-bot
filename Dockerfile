# Host-agnostic image (works on Render, Koyeb, Fly, a VPS, Oracle Cloud, etc.)
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY sunnah_bot.py .
# Token & settings are provided as environment variables / secrets at runtime.
CMD ["python", "-u", "sunnah_bot.py"]
