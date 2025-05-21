# 📰 PR Summarizer: AI-Powered Press Release Monitoring & Summarization System

**PR Summarizer** is a cloud-native application that automates the monitoring, classification, extraction, and summarization of press releases received via email. It leverages Google Cloud Platform (GCP) services and Gemini AI to create an end-to-end system for real-time press release intelligence.

---

## 🧠 Key Features

* 📬 **Gmail Monitoring**: Real-time detection of incoming emails using Gmail API + Pub/Sub.
* 🔎 **Content Extraction**: Inline HTML parsing and URL-based scraping via Crawl4AI.
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

## 🛠 Local Setup Instructions

### Step-by-Step Setup

1. **Clone the Repository (if not already done)**:
   ```bash
   git clone https://github.com/justin-aj/pr-summarizer.git
   cd pr-summarizer
   ```

2. **Set Up Python Virtual Environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Install Playwright Dependencies**:
   ```bash
   playwright install
   ```

4. **Prepare Configuration Files**:
   - Place the following files in the project root directory (`pr-summarizer/`):
     - `credentials.json`: OAuth client secret for Gmail API.
     - `pr-summarizer-key.json`: GCP service account key.
   - Create a `.env` file in the project root with the following content:
     ```env
     PROJECT_ID=your-gcp-project-id
     TOPIC_NAME=your-pubsub-topic
     SUBSCRIPTION_NAME=your-pubsub-subscription
     BUCKET_NAME=your-gcp-bucket-name
     GEMINI_API_KEY=your_gemini_api_key
     ```
     Replace the placeholders (`your-gcp-project-id`, `your-pubsub-topic`, etc.) with your actual GCP project details and Gemini API key.

5. **Create GCP Resources (if not already created)**:
   Even for local usage, the application requires GCP resources (Pub/Sub and Cloud Storage) since it interacts with Gmail API and stores results in GCP. Run the following commands to set up the necessary resources:
   ```bash
   gcloud pubsub topics create your-pubsub-topic --project=your-gcp-project-id
   gcloud pubsub subscriptions create your-pubsub-subscription --topic=your-pubsub-topic --project=your-gcp-project-id
   gsutil mb -p your-gcp-project-id gs://your-gcp-bucket-name
   ```
   Ensure your GCP service account key (`pr-summarizer-key.json`) has permissions for these resources.

6. **Authenticate GCP Locally**:
   Set the `GOOGLE_APPLICATION_CREDENTIALS` environment variable to point to your service account key.

7. **Run the Application**:
   - Execute the `streamer.py` script to start the PR Summarizer:
     ```bash
     python streamer.py
     ```
   - The first time you run it, a browser window will open to authenticate with your Gmail account via OAuth2. Follow the prompts to authorize the application. This will generate a `token.pickle` file in the project root, which will be reused for subsequent runs.

8. **Monitor Output**:
   - The script will monitor your Gmail inbox for new emails, classify them as press releases, extract content, and generate summaries using the Gemini API.
   - Summarized content will be stored as JSON files in the specified GCP Cloud Storage bucket (`your-gcp-bucket-name`).
   - Logs will be written to the console and, if configured, to GCP Cloud Logging.

---

## ⚙️ GCP Deployment Instructions

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
gcloud compute ssh pr-summarizer-vm --zone=us-east1-d

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

0. XXXX - Use your desired name for each application.

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

Authorize with your Gmail account. A `token.pickle` file will be created or upload it after generating it locally.

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

## Latency and Edge Case Handling

### Latency Optimization

1. **Asynchronous Processing**:
   - Uses PubSub for asynchronous message handling
   - Implements AsyncWebCrawler for non-blocking URL scraping
   - Enables parallel processing of multiple message notifications

2. **Selective Content Processing**:
   - Dynamic filtering of HTML content with configurable thresholds
   - Pruning of non-essential content to reduce processing time
   - Focuses only on the newest email messages to minimize processing load

3. **Efficient API Usage**:
   - Uses Gemini 2.0 Flash model for lower-latency AI processing
   - Implements token refresh mechanism to avoid authentication delays
   - Minimizes API calls by early filtering of non-press release content

### Edge Case Handling

1. **Email Format Variations**:
   - Robust handling of multipart MIME types
   - Recursively extracts HTML from nested email parts
   - Supports both HTML and plain text emails with appropriate conversion
   - Fallback mechanisms for poorly structured emails:
     ```python
     if not html_body:
         snippet = msg_data.get('snippet', '')
         if snippet:
             html_body = f"<pre>{snippet}</pre>"
         else:
             html_body = "<pre>No content could be extracted from this email</pre>"
     ```

2. **URL Processing**:
   - Resolves redirects to obtain final destination URLs
   - Handles URL extraction from both href attributes and text content
   - Implements timeout and error handling for URL requests

3. **Content Parsing**:
   - Multiple base64 decoding strategies (URL-safe and standard)
   - BeautifulSoup for robust HTML parsing regardless of formatting
   - Content filtering for removing irrelevant elements (scripts, styles, etc.)

4. **Error Recovery**:
   - Comprehensive try-except blocks throughout the codebase
   - Detailed logging with timestamps for debugging
   - Message acknowledgment handling to prevent data loss

## Scaling Strategy

### Multi-Company Expansion

1. **Configuration-Driven Architecture**:
   - Implement a company configuration file to manage multiple monitoring targets
   - Store company-specific parameters (email filters, domains, classification rules)
   - Enable separate storage paths for each company's results

2. **Parallel Processing Implementation**:
   - Create dedicated Pub/Sub topics and subscriptions per company
   - Implement worker pool with configurable concurrency limits
   - Use Cloud Functions or Cloud Run for scalable processing

### Technical Scaling Approaches

1. **Infrastructure Enhancements**:
   - Migrate to container-based deployment using Cloud Run
   - Implement autoscaling based on Pub/Sub queue depth

2. **Performance Optimizations**:
   ```
   ┌────────────────┐     ┌────────────────┐     ┌────────────────┐
   │ Email Listener │────▶│ Queue Manager  │────▶│ Worker Pool    │
   └────────────────┘     └────────────────┘     └────────────────┘
           │                                              │
           ▼                                              ▼
   ┌────────────────┐                           ┌────────────────┐
   │ Config Manager │                           │ Result Storage │
   └────────────────┘                           └────────────────┘
   ```

3. **Enhanced Monitoring and Reliability**:
   - Implement health checks and automated recovery
   - Set up alerting for processing failures or anomalies
   - Develop a dashboard for monitoring system performance across companies

### Data Handling at Scale

1. **Structured Data Management**:
   - Implement BigQuery or any OLAP integration for analytics across companies
   - Create data retention and archiving policies
   - Develop a standardized schema for cross-company analysis

2. **AI Model Improvements**:
   - Fine-tune classification models for specific industries
   - Implement company-specific summarization templates
   - Build ground truths and then compare the results to generate metrics
