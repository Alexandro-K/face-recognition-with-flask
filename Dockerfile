# ===== base image =====
FROM python:3.11-slim

# Cegah prompt interaktif
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# ===== OS deps untuk OpenCV/dlib =====
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*

# ===== app setup =====
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy source
COPY . .

# Gunicorn (1 worker karena ada global state + streaming)
# Railway akan set PORT, kita forward ke Gunicorn
CMD ["gunicorn", "-w", "1", "-k", "gthread", "--threads", "4", "--timeout", "120", "-b", "0.0.0.0:${PORT}", "app:app"]
