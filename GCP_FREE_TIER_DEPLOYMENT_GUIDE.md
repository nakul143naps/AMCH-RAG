# AMCH-RAG: Google Cloud Platform (GCP) Free Tier Deployment Guide

Google Cloud offers an **"Always Free"** tier that is even better and simpler than AWS:
* **Machine Type**: `e2-micro` (2 vCPUs, 1 GB RAM) &bull; **100% Free Forever** (not limited to 12 months).
* **Storage**: 30 GB standard persistent disk &bull; Free.
* **Eligible US Regions**: `us-central1` (Iowa), `us-east1` (South Carolina), or `us-west1` (Oregon).
* **Zero SSH Setup**: Google Cloud includes a **built-in browser SSH terminal** (click "SSH" in the browser and you're in—no `.pem` files, no PuTTY, no terminal commands needed on your computer).

---

## Step 1: Create a Free VM Instance on Google Cloud

1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. In the top search bar, type **Compute Engine** and select **VM instances**.
   *(If prompted, click "Enable Compute Engine API" - this takes about 30 seconds).*
3. Click the blue **Create Instance** button at the top.
4. Configure these exact settings for Free Tier:
   * **Name**: `amch-rag-server`
   * **Region**: Choose one of the Always Free regions:
     * `us-central1 (Iowa)` **(Recommended)**
     * `us-east1 (South Carolina)`
     * `us-west1 (Oregon)`
   * **Machine configuration**:
     * Series: **E2**
     * Machine type: Select **e2-micro (2 vCPU, 1 GB memory)** *(marked as Free Tier eligible)*.
   * **Boot disk**:
     * Click **Change**.
     * Operating system: **Ubuntu**
     * Version: **Ubuntu 24.04 LTS (x86/64, amd64)**
     * Boot disk type: **Standard persistent disk**
     * Size: **30 GB** (GCP gives 30 GB free per month).
     * Click **Select**.
   * **Firewall** (Crucial):
     * Check **Allow HTTP traffic**
     * Check **Allow HTTPS traffic**
5. Click **Create** at the bottom of the page.
   *(Your instance will start running in ~20 seconds).*

---

## Step 2: Open Ports in the GCP Firewall (1-time step)

By default, Port 80 is open. To also access FastAPI Docs (`8000`) and Qdrant (`6333`):

1. In the GCP top search bar, type **Firewall** and select **VPC network &rarr; Firewall**.
2. Click **Create Firewall Rule** at the top:
   * **Name**: `allow-amch-rag`
   * **Targets**: Select `All instances in the network`
   * **Source IPv4 ranges**: `0.0.0.0/0`
   * **Specified protocols and ports**:
     * Check **TCP** and enter: `80, 8000, 6333`
3. Click **Create**.

---

## Step 3: Connect via 1-Click In-Browser SSH

1. Go back to **Compute Engine &rarr; VM instances**.
2. Look at your `amch-rag-server` row. Under the **Connect** column, click the **SSH** button.
3. A Google Cloud terminal window will automatically pop open inside your browser. No keys or software required!

---

## Step 4: Run the 1-Click Setup Script

In the browser terminal window that popped up, copy and paste these commands:

```bash
# 1. Clone your GitHub repository
git clone https://github.com/nakul143naps/AMCH-RAG.git
cd AMCH-RAG

# 2. Configure your API keys
cp .env.example .env
nano .env
```
In the editor, enter your API keys:
* `GEMINI_API_KEY`: [Google AI Studio](https://aistudio.google.com/app/apikey)
* `GROQ_API_KEY`: [Groq Console](https://console.groq.com/keys)
* `LANGCHAIN_API_KEY`: [LangSmith](https://smith.langchain.com/) (Optional)
* To save and exit in `nano`: Press `Ctrl + O`, then `Enter`, then `Ctrl + X`.

```bash
# 3. Run the automated setup script
chmod +x scripts/setup_gcp_free_tier.sh
./scripts/setup_gcp_free_tier.sh
```

---

## Step 5: Access Your Live Application

The script will configure a **2 GB Swap file**, install Docker, build the unified production container, and launch AMCH-RAG.

Once it completes, copy your instance's **External IP** from the Google Cloud Console (or the script output) and open it in your browser:

* **Web Assistant (React)**: `http://<YOUR_EXTERNAL_IP>`
* **Admin Control Center**: `http://<YOUR_EXTERNAL_IP>/admin`
* **FastAPI Interactive Docs**: `http://<YOUR_EXTERNAL_IP>:8000/docs`
* **Qdrant DB Dashboard**: `http://<YOUR_EXTERNAL_IP>:6333/dashboard`

---

## Useful Maintenance Commands (In Browser SSH)

```bash
# View live application logs
sudo docker compose logs -f app

# Restart services
sudo docker compose restart

# Pull latest updates from GitHub and rebuild
git pull
sudo docker compose up -d --build
```
