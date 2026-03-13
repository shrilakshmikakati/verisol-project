FROM python:3.11-slim

WORKDIR /app

# System deps for spaCy / pytesseract
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr libgl1-mesa-glx curl && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    python -m spacy download en_core_web_sm && \
    python -c "import solcx; solcx.install_solc('0.8.20',show_progress=False)" 2>/dev/null || true

COPY . .

EXPOSE 8000
CMD ["python", "run.py"]
