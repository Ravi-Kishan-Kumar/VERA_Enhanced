FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    PORT=7860 MODEL_DIR=/home/vera/models HF_HOME=/home/vera/.cache/huggingface \
    REDIS_URL=redis://127.0.0.1:6379/0 ENVIRONMENT=production

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 redis-server \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 vera
WORKDIR /app
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install -r /app/backend/requirements.txt
COPY --chown=1000:1000 backend/ /app/backend/
COPY --chown=1000:1000 deploy/huggingface-space/start.sh /app/start.sh
RUN chmod 755 /app/start.sh \
    && mkdir -p /home/vera/models /home/vera/redis \
    && chown -R 1000:1000 /home/vera
USER 1000
WORKDIR /app/backend
EXPOSE 7860
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','7860')+'/health',timeout=4)"
CMD ["/app/start.sh"]
