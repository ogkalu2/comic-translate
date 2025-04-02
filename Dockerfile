FROM nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04

# Evita interazioni durante l'installazione dei pacchetti
ENV DEBIAN_FRONTEND=noninteractive

# Installa dipendenze di sistema
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-dev \
    libgl1-mesa-glx \
    libglib2.0-0 \
    xvfb \
    libnss3 \
    libxcomposite1 \
    libxcursor1 \
    libxi6 \
    libxtst6 \
    libxrandr2 \
    libxss1 \
    libpci3 \
    libglx-mesa0 \
    libegl1 \
    libxkbcommon0 \
    libfontconfig1 \
    libdbus-1-3 \
    libpulse0 \
    pulseaudio \
    sox \
    libsox-fmt-all \
    ffmpeg \
    git \
    x11vnc \
    fluxbox \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Crea directory di lavoro
WORKDIR /app

# Copia i requisiti e installa le dipendenze
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt
RUN pip3 install paddlepaddle-gpu

# Copia il codice dell'applicazione
COPY . .

# Crea password per VNC (default: ctkif25vl)
RUN mkdir -p /root/.vnc && \
    x11vnc -storepasswd ctkif25vl /root/.vnc/passwd

# Script di avvio che usa Xvfb per emulare un display e avvia VNC
RUN echo '#!/bin/bash\nXvfb :1 -screen 0 1920x1080x24 &\nexport DISPLAY=:1\nfluxbox &\nx11vnc -display :1 -forever -usepw -rfbport 5900 &\nexec python3 controller.py "$@"' > /app/start.sh \
    && chmod +x /app/start.sh

# Esponi la porta per VNC
EXPOSE 5900

# Comando predefinito
ENTRYPOINT ["/app/start.sh"]
