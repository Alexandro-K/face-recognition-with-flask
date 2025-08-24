FROM python:3.11-slim

# Install dependencies untuk build dlib & opencv
RUN apt-get update && apt-get install -y \
    build-essential cmake gfortran \
    libopenblas-dev liblapack-dev \
    libx11-dev libgtk-3-dev libboost-all-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

COPY . .

CMD ["gunicorn", "-b", "0.0.0.0:8000", "app:app"]
