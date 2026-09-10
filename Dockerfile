FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    KSB_STATE_FILE=/data/state.json

# adb drives a host emulator; Tesseract enables the march-counter OCR fallback.
RUN apt-get update \
    && apt-get install -y --no-install-recommends adb tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt ./
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt

RUN useradd --create-home --uid 1000 kingshot \
    && mkdir -p /data /app/logs \
    && chown kingshot:kingshot /app /app/logs /data
COPY --chown=kingshot:kingshot . .

USER kingshot
VOLUME ["/data"]

ENTRYPOINT ["python", "main.py"]
CMD ["watch"]
