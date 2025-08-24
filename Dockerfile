FROM python:3.11-slim

# Install dependencies untuk build dlib & opencv
RUN apt-get update && apt-get install -y \
    build-essential cmake gfortran \
    libopenblas-dev liblapack-dev \
    libx11-dev libgtk-3-dev libboost-all-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy & install dependencies
COPY requirements.txt .
RUN pip install --upgrade pip wheel setuptools
RUN pip install -r requirements.txt

# Copy project files
COPY . .

# Gunakan PORT dari env Railway
CMD ["gunicorn", "-b", "0.0.0.0:${PORT}", "app:app"]
