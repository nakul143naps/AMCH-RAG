# AMCH-RAG: AWS EC2 Demo Deployment Guide

This guide describes the portfolio-demo deployment of **AMCH-RAG (Agentic Multi-Modal Corrective Hybrid RAG)** on AWS EC2. AWS pricing and free-tier eligibility vary by account, region, and date; this deployment is not guaranteed to be free.

> **Public demo warning:** the application does not provide complete user authentication or multi-tenant authorization. Anyone who can reach the public app can access its API surface, including document upload and listing. Do not upload resumes, secrets, customer files, or other private documents. Add HTTPS and an authentication layer before accepting private or untrusted-user data.

---

## Demo architecture on AWS EC2

* **Instance Type**: `t2.micro` (or `t3.micro` in supported regions)
* **OS**: Ubuntu 24.04 LTS (x86_64)
* **RAM**: 1 GB Physical + 2 GB Swap (configured automatically by setup script)
* **Storage**: Choose the EBS size for your use case and confirm current AWS pricing.
* **Services Hosted**:
  * **Unified Web App & API** (Port `80`): Serves the React chat application and FastAPI endpoints from one host.
  * **Qdrant Vector Store**: Stores dense and sparse document vectors; its host port is bound to loopback and should not be made public.

---

## Step 1: Launch an AWS EC2 Instance

1. Log into your [AWS Management Console](https://console.aws.amazon.com/).
2. Navigate to **EC2** &rarr; Click **Launch Instance**.
3. Configure the instance:
   * **Name**: `AMCH-RAG-Assistant`
   * **AMI**: `Ubuntu Server 24.04 LTS (HVM), SSD Volume Type` (Free Tier eligible)
   * **Instance Type**: `t2.micro` (1 vCPU, 1 GiB Memory) or `t3.micro`
   * **Key Pair**: Select your existing key pair or click **Create new key pair** (`amch-key.pem`).
4. **Network Settings (Security Group)**:
   * Click **Edit** and allow only the ports required for the demo:
     | Type | Port | Source | Purpose |
     | :--- | :--- | :--- | :--- |
     | **SSH** | `22` | Your current public IP (`/32`) | Restricted administration |
     | **HTTP** | `80` | `0.0.0.0/0` | Public portfolio demo |
   * Do **not** add public inbound rules for `8000`, `6333`, or `6334`. Port 8000 is not needed for the website; Qdrant should remain private.
5. **Configure Storage**:
   * Choose an EBS volume size suitable for your data and confirm the current AWS price before launching.
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
git clone https://github.com/nakul143naps/AMCH-RAG.git
cd AMCH-RAG
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
1. Allocates a **2 GB swap file** to reduce memory pressure on a small instance. Swap does not guarantee that the instance cannot run out of memory.
2. Installs **Docker** and the **Docker Compose plugin**.
3. Builds the production multi-stage Docker container (compiling the React frontend into static assets and packaging FastAPI).
4. Starts Qdrant and the AMCH-RAG service with automatic restart policies.

---

## Step 6: Access Your Live Application

Once completed, open your browser and navigate to:

* **Public Web Assistant**: `http://<YOUR_EC2_PUBLIC_IP>`
* **FastAPI Interactive Docs**: `http://<YOUR_EC2_PUBLIC_IP>/docs` (public API surface; do not expose sensitive operations)
* **Qdrant dashboard**: available from the EC2 host at `http://127.0.0.1:6333/dashboard`; keep it private.

The Compose configuration is for a portfolio demo, not a complete public-service security boundary. The app does not currently enforce full authentication, per-user document access, TLS termination, or durable upload-job processing. Restrict SSH, keep Qdrant private, avoid sensitive uploads, and remove unused AWS resources to avoid ongoing charges.

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
