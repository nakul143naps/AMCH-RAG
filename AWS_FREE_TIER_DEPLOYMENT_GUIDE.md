# AMCH-RAG: AWS Free Tier Deployment Guide

This guide walks you through deploying **AMCH-RAG (Agentic Multi-Modal Corrective Hybrid RAG)** on an **AWS EC2 Free Tier** instance at zero cost.

---

## Architecture on AWS Free Tier

* **Instance Type**: `t2.micro` (or `t3.micro` in supported regions)
* **OS**: Ubuntu 24.04 LTS (x86_64)
* **RAM**: 1 GB Physical + 2 GB Swap (configured automatically by setup script)
* **Storage**: 30 GB gp3 (Free Tier eligible)
* **Services Hosted**:
  * **Unified Web App & API** (Port `80` & `8000`): Serves both the modern React Chat Assistant and the FastAPI RAG backend with zero Node.js overhead.
  * **Native Qdrant Vector Store** (Port `6333`): Lightweight embedded vector database storing dense (bge-small) and sparse (BM25) embeddings.
  * **Admin Cockpit**: Accessible at `/admin` for memory, cache, and guardrail controls.

---

## Step 1: Launch Your AWS EC2 Free Tier Instance

1. Log into your [AWS Management Console](https://console.aws.amazon.com/).
2. Navigate to **EC2** &rarr; Click **Launch Instance**.
3. Configure the instance:
   * **Name**: `AMCH-RAG-Assistant`
   * **AMI**: `Ubuntu Server 24.04 LTS (HVM), SSD Volume Type` (Free Tier eligible)
   * **Instance Type**: `t2.micro` (1 vCPU, 1 GiB Memory) or `t3.micro`
   * **Key Pair**: Select your existing key pair or click **Create new key pair** (`amch-key.pem`).
4. **Network Settings (Security Group)**:
   * Click **Edit** and ensure the following **Inbound Rules** are added:
     | Type | Port | Source | Purpose |
     | :--- | :--- | :--- | :--- |
     | **SSH** | `22` | `My IP` (or `0.0.0.0/0`) | Secure terminal access |
     | **HTTP** | `80` | `0.0.0.0/0` | Web Assistant (React) |
     | **Custom TCP** | `8000` | `0.0.0.0/0` | FastAPI Backend & Docs |
     | **Custom TCP** | `6333` | `My IP` | Qdrant Dashboard (Secure) |
5. **Configure Storage**:
   * Change storage from 8 GB to **30 GB gp3** (Free Tier allows up to 30 GB EBS).
6. Click **Launch Instance**.

---

## Step 2: Connect to Your EC2 Instance

In your local terminal (Windows PowerShell or Git Bash):
```bash
chmod 400 amch-key.pem   # Linux/Mac only
ssh -i "amch-key.pem" ubuntu@<YOUR_EC2_PUBLIC_IP>
```

---

## Step 3: Clone Your GitHub Repository

On the EC2 instance, clone your repository:
```bash
git clone https://github.com/<YOUR_GITHUB_USERNAME>/<YOUR_REPO_NAME>.git
cd <YOUR_REPO_NAME>
```

---

## Step 4: Configure Your Environment Secrets

Create your `.env` file from the example:
```bash
cp .env.example .env
nano .env
```
Fill in your API keys:
* `GEMINI_API_KEY`: [Google AI Studio](https://aistudio.google.com/app/apikey)
* `GROQ_API_KEY`: [Groq Console](https://console.groq.com/keys)
* `LANGCHAIN_API_KEY`: [LangSmith](https://smith.langchain.com/) (Optional)
* Save and exit: Press `Ctrl + O`, then `Enter`, then `Ctrl + X`.

---

## Step 5: Run the 1-Click Setup Script

Make the script executable and run it:
```bash
chmod +x scripts/setup_aws_free_tier.sh
./scripts/setup_aws_free_tier.sh
```

### What this script does automatically:
1. Allocates a **2 GB Swap file** so the 1 GB EC2 instance never encounters Out-Of-Memory issues.
2. Installs **Docker** and the **Docker Compose plugin**.
3. Builds the production multi-stage Docker container (compiling the React frontend into static assets and packaging FastAPI).
4. Starts Qdrant and the AMCH-RAG service with automatic restart policies.

---

## Step 6: Access Your Live Application

Once completed, open your browser and navigate to:

* **Public Web Assistant**: `http://<YOUR_EC2_PUBLIC_IP>` (or `http://<YOUR_EC2_PUBLIC_IP>:8000`)
* **Admin Control Center**: `http://<YOUR_EC2_PUBLIC_IP>/admin`
* **FastAPI Interactive Docs**: `http://<YOUR_EC2_PUBLIC_IP>:8000/docs`
* **Qdrant DB Dashboard**: `http://<YOUR_EC2_PUBLIC_IP>:6333/dashboard`

---

## Useful Maintenance Commands

```bash
# View live application logs
sudo docker compose logs -f app

# View Qdrant logs
sudo docker compose logs -f qdrant

# Restart containers
sudo docker compose restart

# Stop all services
sudo docker compose down

# Update to latest code from GitHub
git pull
sudo docker compose up -d --build
```
