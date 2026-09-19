# AI YouTube Studio - deployable web UI container
# Build:   docker build -t ai-studio .
# Run:     docker run -d --name ai-studio -p 8787:8787 \
#            -v ai-studio-output:/app/output -v ai-studio-runs:/app/runs \
#            --restart unless-stopped ai-studio
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOST=0.0.0.0 \
    PORT=8787

WORKDIR /app

# ffmpeg for the audio/video tools + Noto fonts for Telugu text rendering
# (imageio-ffmpeg ships ffmpeg too; the apt install is a robust fallback)
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg fonts-noto-core fonts-noto-extra \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir faster-whisper \
    || echo "faster-whisper skipped (Tool 3 subtitles unavailable)"

COPY . .

# writeable folders for results, run logs and Whisper model cache
RUN mkdir -p output runs /root/.cache \
    && chmod -R a+rwX output runs

VOLUME ["/app/output", "/app/runs"]

EXPOSE 8787

CMD ["python", "webapp.py"]