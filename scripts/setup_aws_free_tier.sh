#!/usr/bin/env bash
# ==============================================================================
# AMCH-RAG: AWS Free Tier One-Click Deployment Script
# Targets: AWS EC2 t2.micro or t3.micro (Ubuntu 22.04 / 24.04 LTS)
# ==============================================================================

set -e

echo "=========================================================="
echo " Starting AMCH-RAG Setup on AWS Free Tier Instance"
echo "=========================================================="

# 1. Setup 2GB Swap Memory (Crucial for 1GB RAM EC2 Free Tier)
if [ ! -f /swapfile ]; then
    echo "[1/5] Configuring 2GB Swap Memory..."
    sudo fallocate -l 2G /swapfile || sudo dd if=/dev/zero of=/swapfile bs=1M count=2048
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
    echo "vm.swappiness=10" | sudo tee -a /etc/sysctl.conf
    sudo sysctl -p
    echo " Swap configured successfully."
else
    echo "[1/5] Swap file already exists."
fi

# 2. Update System Packages
echo "[2/5] Updating system packages..."
sudo apt-get update -y
sudo apt-get install -y ca-certificates curl gnupg lsb-release git

# 3. Install Docker and Docker Compose Plugin
if ! command -v docker &> /dev/null; then
    echo "[3/5] Installing Docker Engine..."
    sudo install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg --yes
    sudo chmod a+r /etc/apt/keyrings/docker.gpg

    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
      $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
      sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

    sudo apt-get update -y
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

    sudo usermod -aG docker "$USER"
    sudo systemctl enable docker
    sudo systemctl start docker
    echo " Docker installed."
else
    echo "[3/5] Docker is already installed."
fi

# 4. Check for .env file
echo "[4/5] Checking environment configuration..."
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        echo "Creating .env from .env.example..."
        cp .env.example .env
        echo ""
        echo "=========================================================="
        echo " ATTENTION: Please edit .env with your API keys:"
        echo " nano .env"
        echo " Then run: docker compose up -d --build"
        echo "=========================================================="
    else
        echo "Error: .env or .env.example not found!"
        exit 1
    fi
else
    echo " .env file found."
fi

# 5. Build and Launch Containers
echo "[5/5] Building and launching AMCH-RAG containers..."
sudo docker compose down 2>/dev/null || true
sudo docker compose up -d --build

PUBLIC_IP=$(curl -s https://checkip.amazonaws.com || curl -s https://ifconfig.me || echo "your-instance-ip")

echo "=========================================================="
echo " AMCH-RAG is now LIVE on AWS Free Tier!"
echo "=========================================================="
echo " Web Assistant:    http://${PUBLIC_IP}"
echo " Admin Cockpit:    http://${PUBLIC_IP}/admin"
echo " FastAPI Docs:     http://${PUBLIC_IP}/docs"
echo " Qdrant DB:        http://${PUBLIC_IP}:6333/dashboard"
echo "=========================================================="
