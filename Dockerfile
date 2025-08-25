# Gunakan base image Python
FROM python:3.11-slim

# Set env variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install dependencies system untuk dlib, opencv, dsb.
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    libboost-all-dev \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgl1 \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Buat folder kerja
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install pip deps
RUN pip install --no-cache-dir -r requirements.txt

# Copy semua source code
COPY . .

# Expose port (Railway otomatis pakai $PORT)
EXPOSE 8080

# Jalankan dengan Gunicorn
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:${PORT}", "main:app"]
