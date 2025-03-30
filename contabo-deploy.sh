#!/bin/bash

# Script per facilitare il deployment su Contabo
set -e

# Crea le cartelle necessarie
mkdir -p data output config

# Verifica le dipendenze di sistema
check_dependencies() {
  echo "Verifico le dipendenze di sistema..."
  if ! command -v docker &> /dev/null; then
    echo "Docker non è installato. Installazione in corso..."
    sudo apt update
    sudo apt install -y apt-transport-https ca-certificates curl software-properties-common
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
    sudo add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"
    sudo apt update
    sudo apt install -y docker-ce docker-ce-cli containerd.io
    sudo usermod -aG docker $USER
    echo "Docker installato. Riavvia la sessione o esegui 'newgrp docker' per applicare le modifiche al gruppo."
  fi

  if ! command -v docker-compose &> /dev/null; then
    echo "Docker Compose non è installato. Installazione in corso..."
    sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
    echo "Docker Compose installato."
  fi

  # Verifica se è presente una GPU NVIDIA
  if command -v nvidia-smi &> /dev/null; then
    echo "GPU NVIDIA rilevata, configuro NVIDIA Docker..."
    distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
    curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
    curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list
    sudo apt update && sudo apt install -y nvidia-container-toolkit
    sudo systemctl restart docker
  else
    echo "Nessuna GPU NVIDIA rilevata. L'applicazione funzionerà solo con CPU."
    # Modifica docker-compose.yml per rimuovere le configurazioni GPU
    sed -i '/NVIDIA_VISIBLE_DEVICES/d' docker-compose.yml
    sed -i '/deploy:/,/capabilities: \[gpu\]/d' docker-compose.yml
  fi
}

# Avvia l'applicazione
start_application() {
  echo "Avvio CTkif25VL..."
  docker-compose up -d
  
  IP=$(hostname -I | awk '{print $1}')
  echo ""
  echo "=================================================="
  echo "CTkif25VL è in esecuzione!"
  echo ""
  echo "Per accedere all'interfaccia grafica tramite VNC:"
  echo "1. Usa un client VNC e connettiti a: $IP:5900"
  echo "2. Password VNC: ctkif25vl"
  echo ""
  echo "Per modificare la password VNC:"
  echo "docker exec -it ctkif25vl x11vnc -storepasswd NUOVA_PASSWORD /root/.vnc/passwd"
  echo "=================================================="
}

# Menu principale
main() {
  echo "=== CTkif25VL - Deployment Tool ==="
  echo "1. Verifica e installa dipendenze"
  echo "2. Costruisci l'immagine Docker"
  echo "3. Avvia l'applicazione"
  echo "4. Ferma l'applicazione"
  echo "5. Visualizza logs"
  echo "6. Esegui tutte le operazioni (1-3)"
  echo "q. Esci"
  
  read -p "Seleziona un'opzione: " choice
  
  case $choice in
    1) check_dependencies ;;
    2) docker-compose build ;;
    3) start_application ;;
    4) docker-compose down ;;
    5) docker-compose logs -f ;;
    6) 
      check_dependencies
      docker-compose build
      start_application
      ;;
    q) exit 0 ;;
    *) echo "Opzione non valida" ;;
  esac
  
  echo ""
  main
}

# Avvio del menu
main
