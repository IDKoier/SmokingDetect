FROM nvidia/cuda:11.8.0-base-ubuntu22.04

WORKDIR /app

RUN apt-get update && apt-get install -y \
	libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    python3 \
    python3-pip \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

VOLUME /app/photo

CMD ["python3", "sever.py"]