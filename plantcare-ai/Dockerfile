FROM python:3.11-slim

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libgomp1 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# torch CPU allégé pour l'image (retire si tu déploies avec GPU)
RUN pip install --no-cache-dir -r requirements.txt

# Option A — SDK Gemini (couche séparée : évite de réinstaller torch au rebuild)
RUN pip install --no-cache-dir google-generativeai

COPY . .
ENV PYTHONPATH=/app/src
EXPOSE 8000
CMD ["uvicorn", "plantcare.api.main:app", "--host", "0.0.0.0", "--port", "8000"]