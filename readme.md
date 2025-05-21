# 📰 PR Summarizer: AI-Powered Press Release Monitoring & Summarization System

**PR Summarizer** is a cloud-native application that automates the monitoring, classification, extraction, and summarization of press releases received via email. It leverages Google Cloud Platform (GCP) services and Gemini AI to create an end-to-end system for real-time press release intelligence.

---

## 🧠 Key Features

* 📬 **Gmail Monitoring**: Real-time detection of incoming emails using Gmail API + Pub/Sub.
* 🔎 **Content Extraction**: Inline HTML parsing and URL-based scraping via Playwright & Crawl4AI.
* 🧾 **AI Classification & Summarization**: Uses Gemini 2.0 Flash to:

  * Classify whether an email is a press release
  * Identify content type (inline or linked)
  * Extract publication timestamps
  * Generate concise summaries
    
* ☁️ **Cloud Storage & Logging**: Summarized content stored as structured JSON in GCP buckets, with full Cloud Logging support.
* ⚙️ **Asynchronous Architecture**: Designed with Pub/Sub and asyncio for efficient, scalable processing.
* 🛠 **Edge Case Resilience**: Robust to MIME types, malformed HTML, delayed loads, missing headers, and unstructured emails.

---

## 🏗 Architecture Overview

```text
┌─────────────────┐        ┌───────────────┐        ┌───────────────────┐
│ Gmail Service   │───────▶│ Pub/Sub Topic │───────▶│ Subscriber Client │
└─────────────────┘        └───────────────┘        └─────────┬─────────┘
                                                              │
                                                              ▼
                                                   ┌───────────────────┐
                                                   │ Email Processing  │
                                                   └─────────┬─────────┘
                                                             │
                                                             ▼
┌─────────────────┐                               ┌───────────────────┐
│ Gmail API       │◀──────────────────────────────│ Message Fetching  │
└─────────────────┘                               └─────────┬─────────┘
                                                            │
                                                            ▼
┌─────────────────┐                               ┌───────────────────┐
│ Crawl4ai        │◀──────────────────────────────│ URL Scraping      │
└─────────────────┘                               └─────────┬─────────┘
                                                            │
                                                            ▼
┌─────────────────┐                               ┌───────────────────┐
│ Gemini API      │◀──────────────────────────────│ Content Analysis  │
└─────────────────┘                               └─────────┬─────────┘
                                                            │
                                                            ▼
┌─────────────────┐                               ┌───────────────────┐
│ Cloud Storage   │◀──────────────────────────────│ Result Storage    │
└─────────────────┘                               └───────────────────┘
```

---

## ⚙️ Deployment Instructions

### Prerequisites

* Gmail account + OAuth2 credentials
* Google Cloud project with:

  * Pub/Sub
  * Cloud Storage
  * Logging enabled
* Gemini API key
* A VM instance or compute environment with Python 3.9+

### GCP VM Setup

```bash
# Create VM
gcloud compute instances create pr-summarizer-vm \
  --machine-type=e2-medium \
  --zone=us-east1-d \
  --image-family=debian-11 \
  --image-project=debian-cloud \
  --boot-disk-size=30GB

# SSH into VM
gcloud compute ssh pr-summarizer-vm --zone=us-east1-a

# Install packages
sudo apt update && sudo apt install -y python3-pip python3-venv git
```

### Environment Setup

```bash
# Clone repo
git clone https://github.com/justin-aj/pr-summarizer.git
cd pr-summarizer

# Python virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Install Playwright dependencies
playwright install
```

### Configuration

1. Create a `.env` file:

```env
PROJECT_ID=XXXXXX
TOPIC_NAME=XXXXXXX
SUBSCRIPTION_NAME=XXXXXX
BUCKET_NAME=prsummarized-files
GEMINI_API_KEY=your_gemini_api_key
```

2. Add credentials to the project root:

   * `credentials.json` (OAuth client secret for Gmail API)
   * `pr-summarizer-key.json` (GCP service account key)

3. Create GCP resources(can be done early on too):

```bash
gcloud pubsub topics create XXXXX --project=XXXXXX
gcloud pubsub subscriptions create XXXXX --topic=XXXXX --project=XXXXX
gsutil mb -p utilitarian-mix-459622-c9 gs://prsummarized-files
```

---

## 🚀 Running the Application

### First-Time OAuth Flow (browser required)

```bash
python streamer.py
```

Authorize with your Gmail account. A `token.pickle` file will be created.

### Run as a background service

```bash
cat > pr-summarizer.service << EOF
[Unit]
Description=PR Summarizer Service
After=network.target

[Service]
User=your-username
WorkingDirectory=/home/your-username/pr-summarizer
ExecStart=/home/your-username/pr-summarizer/venv/bin/python streamer.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo mv pr-summarizer.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable pr-summarizer
sudo systemctl start pr-summarizer
```

### Monitoring the Service

```bash
sudo systemctl status pr-summarizer
sudo journalctl -u pr-summarizer -f
```

---

## ⚡️ Performance & Edge Case Handling

### Latency Optimization

* **Asynchronous pipeline** via Pub/Sub and async URL fetches
* **Selective filtering** to discard irrelevant content early
* **Efficient Gemini API usage** to reduce token consumption

### Edge Case Management

* Handles nested MIME structures, inline HTML, malformed dates
* Resilient to JS-heavy pages and missing meta content
* Filters bot-generated or non-news content

---



