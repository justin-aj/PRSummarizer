# PR Summarizer Application Documentation

## Architecture Overview

The PR Summarizer is a cloud-based application designed to automatically process emails containing press releases, extract their content, classify them, and generate concise summaries. The system leverages Google Cloud Platform services and AI capabilities to provide an end-to-end solution for press release monitoring and summarization.

### System Components

```
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

### Key Components:

1. **Gmail Integration**:
   - Uses Gmail API to authenticate and access emails
   - Sets up watch notifications to detect new emails

2. **Message Processing Pipeline**:
   - Pub/Sub for message notifications and queue management
   - Email content parsing and HTML extraction
   - URL resolution and content scraping with Crawl4ai

3. **AI Classification and Summarization**:
   - Gemini 2.0 Flash model for:
     - Press release classification (YES/NO)
     - Type determination (inline/URL)
     - Timestamp or date retrieval
     - Content summarization

4. **Storage and Logging**:
   - Google Cloud Storage for storing processed results
   - Cloud Logging for application monitoring
   - Structured error handling and logging

### Data Flow:

1. Application initializes Gmail API watch for new messages
2. When a new email arrives, Gmail sends a notification to Pub/Sub
3. Subscriber receives notification and processes the newest email
4. Email content is parsed and analyzed for press release indicators
5. If classified as a press release:
   - For inline content: Extract from email body
   - For URL content: Scrape the referenced webpage
6. Press release content is summarized using Gemini AI
7. Results are saved to Cloud Storage in a structured JSON format
8. Comprehensive logging throughout the process

## Deployment Instructions

### Prerequisites

- Google Cloud Platform account
- Gmail account with OAuth2 credentials
- Gemini API key
- Service account with appropriate permissions

### Environment Setup on GCP VM Instance

1. **Create a VM Instance**:
   ```bash
   gcloud compute instances create pr-summarizer-vm \
     --machine-type=e2-medium \
     --zone=us-east1-d \
     --image-family=debian-11 \
     --image-project=debian-cloud \
     --boot-disk-size=20GB
   ```

2. **SSH into the VM**:
   ```bash
   gcloud compute ssh pr-summarizer-vm --zone=us-east1-a
   ```

3. **Install required packages**:
   ```bash
   sudo apt-get update
   sudo apt-get install -y python3-pip python3-venv git
   ```

4. **Clone the repository**:
   ```bash
   git clone https://github.com/justin-aj/pr-summarizer.git
   cd pr-summarizer
   ```

5. **Set up Python environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

### Configuration

1. **Create .env file**:
   ```bash
   cat > .env << EOF
   PROJECT_ID=utilitarian-mix-459622-c9
   TOPIC_NAME=gmail-alerts
   SUBSCRIPTION_NAME=gmail-alerts-sub
   BUCKET_NAME=prsummarized-files
   GEMINI_API_KEY=your_gemini_api_key
   EOF
   ```

2. **Place credential files in the project directory**:
   - `credentials.json` (OAuth client ID for Gmail)
   - `pr-summarizer-key.json` (Service account key)

3. **Install Playwright for Crawl4AI**
   -  Run `playwright install`

3. **Set up Pub/Sub topic and subscription**:
   ```bash
   gcloud pubsub topics create gmail-alerts --project=utilitarian-mix-459622-c9
   gcloud pubsub subscriptions create gmail-alerts-sub --topic=gmail-alerts --project=utilitarian-mix-459622-c9
   ```

4. **Create Cloud Storage bucket**:
   ```bash
   gsutil mb -p utilitarian-mix-459622-c9 gs://prsummarized-files
   ```

### Running the Application

1. **First-time setup (requires browser for OAuth)**:
   - Use SSH with port forwarding or run on a machine with a GUI
   - Run the application to complete OAuth flow:
     ```bash
     python streamer.py
     ```
   - Follow the OAuth prompts to authorize the application
   - This will create a `token.pickle` file or generate it locally and upload it to the directory

2. **Set up as a background service**:
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

3. **Monitor the service**:
   ```bash
   sudo systemctl status pr-summarizer
   sudo journalctl -u pr-summarizer -f
   ```

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
