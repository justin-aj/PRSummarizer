import asyncio
import base64
import email
import json
import logging
import os
import pickle
import re
from datetime import datetime, timezone

import google.generativeai as genai
from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.cloud import logging as cloud_logging
from google.cloud import pubsub_v1
from google.cloud import storage
from google.cloud.logging_v2.handlers import CloudLoggingHandler
from google.oauth2 import service_account
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth import jwt
import requests
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

# Timestamp to print statements for better debugging
def print_with_timestamp(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-2]
    print(f"[{timestamp}] {message}")

# Load environment variables
load_dotenv()
PROJECT_ID = os.getenv("PROJECT_ID", 'utilitarian-mix-459622-c9')
TOPIC_NAME = os.getenv("TOPIC_NAME", 'gmail-alerts')
SUBSCRIPTION_NAME = os.getenv("SUBSCRIPTION_NAME", 'gmail-alerts-sub')
BUCKET_NAME = os.getenv("BUCKET_NAME", "prsummarized-files")
RESULTS_PREFIX = "press-release-results/"

print_with_timestamp(f"Starting application with PROJECT_ID: {PROJECT_ID}")
print_with_timestamp(f"TOPIC_NAME: {TOPIC_NAME}, SUBSCRIPTION_NAME: {SUBSCRIPTION_NAME}")
print_with_timestamp(f"BUCKET_NAME: {BUCKET_NAME}, RESULTS_PREFIX: {RESULTS_PREFIX}")

# Gmail API scopes
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly',
          'https://www.googleapis.com/auth/pubsub']
print_with_timestamp(f"Using API scopes: {SCOPES}")

# Google Cloud Logging client with service account credentials
print_with_timestamp("Setting up Google Cloud Logging client")
credentials = service_account.Credentials.from_service_account_file("pr-summarizer-key.json")
cloud_client = cloud_logging.Client(credentials=credentials, project=PROJECT_ID)

audience = "https://pubsub.googleapis.com/google.pubsub.v1.Subscriber"
credentials_jwt = jwt.Credentials.from_signing_credentials(
    credentials, audience=audience
)
print_with_timestamp("JWT credentials created for Pub/Sub")

# Cloud Logging handler
cloud_handler = CloudLoggingHandler(cloud_client)
formatter = logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
)
cloud_handler.setFormatter(formatter)

# Configure the root logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(cloud_handler)
print_with_timestamp("Logger configured with Cloud Logging handler")

# Gemini Setup
print_with_timestamp("Configuring Gemini API")
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
gemini_model = genai.GenerativeModel("models/gemini-2.0-flash")
print_with_timestamp("Gemini API initialized with model: models/gemini-2.0-flash")


class TimestampRetainingFilter(PruningContentFilter):
    # Define common timestamp patterns
    TIMESTAMP_PATTERNS = [
        r'\b\d{4}-\d{2}-\d{2}\b',  # e.g., 2025-05-20
        r'\b[A-Za-z]+ \d{1,2}, \d{4}\b',  # e.g., May 20, 2025
        r'\b\d{1,2} [A-Za-z]+ \d{4}\b',  # e.g., 20 May 2025
        # Add more patterns as needed based on your websites
    ]

    def should_retain(self, node):
        # Text content of the node
        text = node.text_content()
        # Check if the text matches any timestamp pattern
        for pattern in self.TIMESTAMP_PATTERNS:
            if re.search(pattern, text):
                return True
        # If no timestamp is found, use the default pruning logic
        return super().should_retain(node)

# Crawl4ai scraping function
async def async_scrape_url(url):
    logger.info(f"Starting URL scrape: {url}")
    print_with_timestamp(f"Starting URL scrape: {url}")
    try:
        # Step 1: Create a custom pruning filter that retains timestamps
        prune_filter = TimestampRetainingFilter(
            threshold=0.3,  # Lower → more content retained, higher → more content pruned
            threshold_type="dynamic",  # "fixed" or "dynamic"
            min_word_threshold=5
        )
        # Step 2: Insert it into a Markdown Generator
        md_generator = DefaultMarkdownGenerator(content_filter=prune_filter)

        # Step 3: Pass it to CrawlerRunConfig
        config = CrawlerRunConfig(
            markdown_generator=md_generator
        )

        async with AsyncWebCrawler() as crawler:
            print_with_timestamp(f"AsyncWebCrawler initialized for URL: {url}")
            result = await crawler.arun(url=url, config=config)
            logger.info(f"Successfully scraped URL: {url}")
            print_with_timestamp(
                f"Successfully scraped URL: {url}, content length: {len(result.markdown) if result.markdown else 0}")
            return result.markdown.fit_markdown
    except Exception as e:
        logger.error(f"Scraping error for {url}: {str(e)}")
        print_with_timestamp(f"ERROR: Scraping error for {url}: {str(e)}")
        return None


def sync_scrape_url(url):
    print_with_timestamp(f"Running synchronous URL scrape for: {url}")
    return asyncio.run(async_scrape_url(url))


# Gmail Auth with token refresh and scope management
def get_gmail_service():
    logger.info("Initializing Gmail service")
    print_with_timestamp("Initializing Gmail service")
    creds = None
    if os.path.exists('token.pickle'):
        print_with_timestamp("Found existing token.pickle file")
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
            print_with_timestamp(f"Loaded credentials from token.pickle, valid: {creds.valid if creds else False}")

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logger.info("Refreshing expired credentials")
            print_with_timestamp("Refreshing expired credentials")
            creds.refresh(Request())
            print_with_timestamp("Credentials refreshed successfully")
        else:
            logger.info("Creating new credentials flow")
            print_with_timestamp("Creating new credentials flow with client secrets file")
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            print_with_timestamp("Starting local server flow for authentication")
            creds = flow.run_local_server(port=0)
            print_with_timestamp("Authentication flow completed successfully")
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
            logger.info("Saved new credentials to token.pickle")
            print_with_timestamp("Saved new credentials to token.pickle")

    print_with_timestamp("Building Gmail API service")
    service = build('gmail', 'v1', credentials=creds)
    logger.info("Gmail service initialized successfully")
    print_with_timestamp("Gmail service initialized successfully")
    return service


def parse_email_content(msg_data):
    logger.info("Parsing email content")
    print_with_timestamp("Parsing email content")
    headers = msg_data['payload'].get('headers', [])
    subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), '')
    date_raw = next((h['value'] for h in headers if h['name'].lower() == 'date'), '')

    print_with_timestamp(f"Email subject: {subject}")

    timestamp = ''
    if date_raw:
        try:
            timestamp = email.utils.parsedate_to_datetime(date_raw).astimezone(timezone.utc).isoformat()
            print_with_timestamp(f"Parsed email timestamp: {timestamp}")
        except Exception as e:
            timestamp = datetime.now(timezone.utc).isoformat()
            logger.warning("Failed to parse email date, using current timestamp")
            print_with_timestamp(f"WARNING: Failed to parse email date, using current timestamp: {str(e)}")

    payload = msg_data.get('payload', {})
    mime_type = payload.get('mimeType', '')
    parts = payload.get('parts', [])
    print_with_timestamp(f"Email MIME type: {mime_type}, has parts: {len(parts) > 0}")

    def decode_body(data):
        """Decode base64 encoded email content"""
        if not data:
            print_with_timestamp("WARNING: Empty data provided to decode_body")
            return ''

        try:
            try:
                decoded = base64.urlsafe_b64decode(data).decode('utf-8')
                print_with_timestamp(f"Successfully decoded body, length: {len(decoded)}")
                return decoded
            except Exception as e:
                print_with_timestamp(f"URL-safe decode failed, trying standard base64: {str(e)}")
                decoded = base64.b64decode(data).decode('utf-8')
                print_with_timestamp(f"Successfully decoded with standard base64, length: {len(decoded)}")
                return decoded
        except Exception as e:
            logger.warning(f"Failed to decode email body: {str(e)}")
            print_with_timestamp(f"WARNING: Failed to decode email body: {str(e)}")
            return ''

    def extract_html(parts):
        """Recursively extract HTML from email parts, preserving all HTML content including URLs"""
        print_with_timestamp(f"Extracting HTML from {len(parts)} parts")

        html_content = None
        plain_content = None

        for part in parts:
            part_type = part.get('mimeType', '')
            print_with_timestamp(f"Processing part with MIME type: {part_type}")

            if part_type == 'text/html':
                print_with_timestamp("Found HTML part")
                body_data = part.get('body', {}).get('data', '')
                if body_data:
                    html_content = decode_body(body_data)
                    print_with_timestamp(f"HTML content extracted, length: {len(html_content)}")
                    return html_content
            elif part_type == 'text/plain':
                body_data = part.get('body', {}).get('data', '')
                if body_data:
                    plain_content = decode_body(body_data)
                    print_with_timestamp(f"Plain text content extracted, length: {len(plain_content)}")
            elif part_type.startswith('multipart') and 'parts' in part:
                print_with_timestamp(f"Found nested multipart, recursing into {len(part['parts'])} child parts")
                nested = extract_html(part['parts'])
                if nested:
                    return nested

        if plain_content and not html_content:
            print_with_timestamp("Converting plain text to HTML")
            return f"<pre>{plain_content}</pre>"

        print_with_timestamp("No HTML content found in any parts")
        return ''

    html_body = ''
    if mime_type.startswith('multipart'):
        print_with_timestamp("Processing multipart email")
        html_body = extract_html(parts)
    elif mime_type == 'text/html':
        print_with_timestamp("Processing HTML email")
        body_data = payload.get('body', {}).get('data', '')
        if body_data:
            html_body = decode_body(body_data)
            print_with_timestamp(f"Direct HTML body extracted, length: {len(html_body)}")
        else:
            print_with_timestamp("No body data found in HTML email")
    elif mime_type == 'text/plain':
        print_with_timestamp("Processing plain text email")
        body_data = payload.get('body', {}).get('data', '')
        if body_data:
            plain_text = decode_body(body_data)
            html_body = f"<pre>{plain_text}</pre>"
            print_with_timestamp(f"Converted plain text to HTML, length: {len(html_body)}")
        else:
            print_with_timestamp("No body data found in plain text email")
    else:
        print_with_timestamp(f"Unhandled MIME type: {mime_type}")
        body_data = payload.get('body', {}).get('data', '')
        if body_data:
            html_body = decode_body(body_data)
            print_with_timestamp(f"Extracted content from unknown MIME type, length: {len(html_body)}")

    # Final check for HTML body
    if not html_body:
        print_with_timestamp("WARNING: No HTML body was extracted from email")
        snippet = msg_data.get('snippet', '')
        if snippet:
            print_with_timestamp(f"Using message snippet as fallback, length: {len(snippet)}")
            html_body = f"<pre>{snippet}</pre>"
        else:
            html_body = "<pre>No content could be extracted from this email</pre>"
    else:
        # Verify HTML contains proper tags
        sample_tags = ['<html', '<body', '<div', '<p', '<a', '<table', '<img']
        found_tags = [tag for tag in sample_tags if tag in html_body.lower()]
        print_with_timestamp(f"HTML tags found in content: {found_tags}")

    print_with_timestamp(f"Email parsing complete, HTML body length: {len(html_body)}")
    logger.info("Email content parsed successfully")

    return {'subject': subject, 'timestamp': timestamp, 'html': html_body}

# Function to resolve final URL
def resolve_urls(url_list):
    resolved_urls = []
    for url in url_list:
        try:
            response = requests.get(url, allow_redirects=True, timeout=5)
            resolved_urls.append(response.url)
        except requests.exceptions.RequestException as e:
            resolved_urls.append(f"Error: {e}")
    return resolved_urls


def process_html_content(html):
    logger.info("Processing HTML content")
    print_with_timestamp("Processing HTML content")
    try:
        soup = BeautifulSoup(html, 'html.parser')
        for tag in soup(['script', 'style', 'nav', 'footer', 'header']):
            tag.decompose()
        urls = [a.get('href') for a in soup.find_all('a', href=True)]
        body = ' '.join(soup.stripped_strings)[:1000]
        text_urls = re.findall(r'https?://\S+', soup.get_text())
        all_urls = list(set(urls + text_urls))
        final_urls = resolve_urls(all_urls)
        return body, final_urls
    except Exception as e:
        logger.error(f"Error processing HTML: {str(e)}")
        print_with_timestamp(f"ERROR: Error processing HTML: {str(e)}")
        return "", []


# Gemini Prompt
def construct_prompt(subject, body, urls):
    logger.debug(f"URLS found in email: {urls}")
    print("URLS", urls)
    return f"""
        Prompt:

        You are given the content of an email. Classify whether the email is a press release. A press release is a formal announcement about company news, product launches, partnerships, or significant events, and is intended for public or media distribution. Do not classify stock updates, investor alerts, promotional emails, or subscription notices as press releases.

        Return only a raw JSON object in the following format (on a single line):

        {{
        "press_release": "YES" or "NO",
        "type": "inline" (if the press release content is in the email body), "url" (if it's in a linked page), or null,
        "url": a string (if type is "url"), otherwise null,
        "text": the main body of the press release as a string (if type is "inline"), otherwise null,
        "timestamp": the release date in YYYY-MM-DD format (if type is "inline"), otherwise null
        }}

        Rules:
        1. Preserve URLs exactly as received
        2. Never modify URL casing/parameters
        3. Return raw JSON without markdown
        4. For 'inline' type, extract the release date or timestamp from the email body and set 'timestamp'. If the date cannot be determined, set 'timestamp' to null.

        Examples:

        {{"press_release": "YES", "type": "inline", "url": null, "text": "New York, NY - May 20, 2025 - Company XYZ announces...", "timestamp": "2025-05-20"}}
        {{"press_release": "YES", "type": "url", "url": "https://xyz.com/press-release", "text": null, "timestamp": null}}
        {{"press_release": "NO", "type": null, "url": null, "text": null, "timestamp": null}}

        Input:

        SUBJECT: {subject}
        BODY: {body[:1000]}
        URLS: {'   ,   '.join(urls) if urls else 'None'}

        Only return a single-line raw JSON response. Do not include code blocks or markdown.
        """


def call_gemini(prompt):
    logger.info("Calling Gemini API")
    print_with_timestamp("Calling Gemini API")
    try:
        print_with_timestamp(f"Sending prompt to Gemini, length: {len(prompt)}")
        response = gemini_model.generate_content(prompt)
        print_with_timestamp(f"Received response from Gemini, text: {response.text[:100]}...")

        result = json.loads(response.text.strip())
        logger.info("Gemini API call successful")
        print_with_timestamp(f"Gemini API call successful, parsed JSON: {result}")
        return result
    except Exception as e:
        logger.error(f"Gemini API error: {str(e)}")
        print_with_timestamp(f"ERROR: Gemini API error: {str(e)}")
        return {"press_release": "NO", "type": None, "url": None, "text": None}


# Summarization
def summarize_text(text):
    logger.info("Generating summary")
    print_with_timestamp(f"Generating summary for text of length: {len(text)}")
    prompt = f"""
            Prompt:
        
                You are given a press release. Summarize the content with a concise structured summary.
        
                Return a single-line raw JSON object in the following format (do NOT include triple backticks or any formatting):
        
                "headline": a short, informative title based on the press release
        
                "key_result": a concise statement of the main outcome or news
        
                "impacted_program": the specific program, initiative, or area affected
        
                "next_step": the immediate follow-up action or implication mentioned
                
                "timestamp": the release date in date format or timestamp format, or null if not found
        
            TEXT:
        
                {text}
        
            Only return a single-line raw JSON object. Do not include triple quotes, code blocks, or markdown.
        """

    try:
        print_with_timestamp("Sending summarization prompt to Gemini")
        response = gemini_model.generate_content(prompt)
        print_with_timestamp(f"Received summarization response: {response.text[:100]}...")

        result = json.loads(response.text.strip())
        logger.info("Summary generated successfully")
        print_with_timestamp(f"Summary generated successfully: {result.get('headline', '')}")
        return result
    except Exception as e:
        logger.error(f"Summarization error: {str(e)}")
        print_with_timestamp(f"ERROR: Summarization error: {str(e)}")
        return {"headline": "", "key_result": "", "impacted_program": "", "next_step": ""}


# Renew watch (Gmail notifications expire after 7 days)
def renew_watch(service):
    """Renew Gmail API push notifications (to be called every 5-6 days)."""
    logger.info("Renewing Gmail watch")
    print_with_timestamp("Renewing Gmail watch")
    try:
        history_id = setup_watch(service)
        print_with_timestamp(f"Gmail watch renewed successfully with historyId: {history_id}")
        return history_id
    except Exception as e:
        logger.error(f"Failed to renew Gmail watch: {str(e)}")
        print_with_timestamp(f"ERROR: Failed to renew Gmail watch: {str(e)}")
        return None


# Save to GCS
def save_to_gcs(data, filename):
    logger.info(f"Saving to GCS: {filename}")
    print_with_timestamp(f"Saving to GCS: {filename}")
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(RESULTS_PREFIX + filename)

        if isinstance(data, dict):
            data = json.dumps(data, indent=2)
            print_with_timestamp(f"Converted dict to JSON string, length: {len(data)}")

        print_with_timestamp(f"Uploading to gs://{BUCKET_NAME}/{RESULTS_PREFIX}{filename}")
        blob.upload_from_string(data, content_type="application/json")
        logger.info(f"Successfully saved to gs://{BUCKET_NAME}/{RESULTS_PREFIX}{filename}")
        print_with_timestamp(f"Successfully saved to gs://{BUCKET_NAME}/{RESULTS_PREFIX}{filename}")
        return True
    except Exception as e:
        logger.error(f"Failed to save to GCS: {str(e)}")
        print_with_timestamp(f"ERROR: Failed to save to GCS: {str(e)}")
        return False


# Process a single email message - modified to match the requested JSON structure
def process_email_message(service, message_id):
    logger.info(f"Processing email message: {message_id}")
    print_with_timestamp(f"Processing email message: {message_id}")
    try:
        print_with_timestamp(f"Fetching message data for ID: {message_id}")
        msg_data = service.users().messages().get(userId='me', id=message_id).execute()
        print_with_timestamp(f"Successfully fetched message data, snippet: {msg_data.get('snippet', '')[:50]}...")

        email_info = parse_email_content(msg_data)
        print_with_timestamp(f"Email parsed, subject: {email_info['subject']}")

        # Extract sender
        headers = msg_data['payload'].get('headers', [])
        sender = next((h['value'] for h in headers if h['name'].lower() in ['from', 'sender']), '')
        print_with_timestamp(f"Email sender: {sender}")

        body, urls = process_html_content(email_info['html'])
        print_with_timestamp(f"HTML processed, body length: {len(body)}, URLs count: {len(urls)}")

        print_with_timestamp("Constructing prompt for classification")
        prompt = construct_prompt(email_info['subject'], body, urls)

        classification = call_gemini(prompt)
        print_with_timestamp(f"Classification result: {classification}")

        summary = {}
        press_release_text = None
        press_release_url = None

        if classification['press_release'] == "YES":
            print_with_timestamp("Email classified as press release, processing content")
            text = None
            if classification['type'] == 'inline':
                print_with_timestamp("Using inline text for press release")
                text = str(body)
                press_release_text = text
                press_release_website_timestamp = classification['timestamp']
            elif classification['type'] == 'url' and classification['url']:
                logger.info(f"Scraping URL for press release: {classification['url']}")
                print_with_timestamp(f"Scraping URL for press release: {classification['url']}")
                press_release_url = classification['url']
                text = sync_scrape_url(classification['url'])
                print_with_timestamp(f"URL scraping complete, text length: {len(text) if text else 0}")
                press_release_text = text

            if text:
                print_with_timestamp("Generating summary from press release text")
                summary = summarize_text(text)
                press_release_website_timestamp = summary.get('timestamp', '')
                logger.info(f"Generated summary: {summary.get('headline', '')}")
                print_with_timestamp(f"Generated summary: {summary.get('headline', '')}")
            else:
                print_with_timestamp("No text content available for summarization")
        else:
            print_with_timestamp("Email not classified as press release, skipping summarization")

        # New result structure that matches the requested format
        result = {
            "press_release_website_timestamp": press_release_website_timestamp,
            "email_timestamp": email_info['timestamp'],
            "retrieval_timestamp": datetime.now(timezone.utc).isoformat(),
            "summary_timestamp": datetime.now(timezone.utc).isoformat(),
            "email_subject": email_info['subject'],
            "email_sender": sender,
            "press_release_url": press_release_url,
            "press_release_text": press_release_text,
            "llm_summary": summary  # This already has headline, key_result, impacted_program, next_step
        }

        print_with_timestamp(f"Processing complete, result: {json.dumps(result, indent=2)[:200]}...")

        filename = f"{message_id}.json"
        save_to_gcs(result, filename)
        logger.info(f"Completed processing email: {message_id}")
        print_with_timestamp(f"Completed processing email: {message_id}")
        return result
    except Exception as e:
        logger.error(f"Error processing email {message_id}: {str(e)}")
        print_with_timestamp(f"ERROR: Error processing email {message_id}: {str(e)}")
        import traceback
        print_with_timestamp(f"Traceback: {traceback.format_exc()}")
        return {}


def setup_watch(service):
    """Set up Gmail API push notifications to Pub/Sub."""
    logger.info("Setting up Gmail watch")
    print_with_timestamp("Setting up Gmail watch")

    publisher = pubsub_v1.PublisherClient(credentials=credentials)

    topic_path = publisher.topic_path(PROJECT_ID, TOPIC_NAME)
    print_with_timestamp(f"Using Pub/Sub topic: {topic_path}")

    try:
        publisher.get_topic(request={"topic": topic_path})
        logger.info(f"Topic {topic_path} already exists")
        print_with_timestamp(f"Topic {topic_path} already exists")
    except Exception as e:
        print_with_timestamp(f"Topic {topic_path} does not exist, creating it now: {str(e)}")
        publisher.create_topic(request={"name": topic_path})
        logger.info(f"Created topic {topic_path}")
        print_with_timestamp(f"Created topic {topic_path}")

    # Watch request
    request = {
        'labelIds': ['INBOX'],
        'topicName': f'projects/{PROJECT_ID}/topics/{TOPIC_NAME}'
    }
    print_with_timestamp(f"Watch request: {request}")

    try:
        print_with_timestamp("Sending watch request to Gmail API")
        response = service.users().watch(userId='me', body=request).execute()
        history_id = response['historyId']
        logger.info(f"Gmail watch setup successful with historyId: {history_id}")
        print_with_timestamp(f"Gmail watch setup successful with historyId: {history_id}")
        print_with_timestamp(f"Full watch response: {response}")
        return history_id
    except Exception as e:
        logger.error(f"Gmail watch setup failed: {str(e)}")
        print_with_timestamp(f"ERROR: Gmail watch setup failed: {str(e)}")
        raise


# Pub/Sub subscriber
def process_pubsub_message(service):
    logger.info("Starting Pub/Sub message processing (legacy mode)")
    print_with_timestamp("Starting Pub/Sub message processing (legacy mode)")
    subscriber = pubsub_v1.SubscriberClient(credentials=credentials_jwt)
    subscription_path = subscriber.subscription_path(PROJECT_ID, SUBSCRIPTION_NAME)
    print_with_timestamp(f"Using subscription: {subscription_path}")

    def callback(message):
        logger.info(f"Received Pub/Sub message: {message.message_id}")
        print_with_timestamp(f"Received Pub/Sub message: {message.message_id}")
        try:
            raw_data = message.data
            decoded_data = raw_data.decode('utf-8', errors='ignore')
            print_with_timestamp(f"Decoded data: {decoded_data[:100]}...")

            try:
                data = json.loads(decoded_data)
                print_with_timestamp(f"Parsed JSON data: {json.dumps(data, indent=2)[:200]}...")
            except json.JSONDecodeError as e:
                logger.error(f"JSON parse error: {str(e)}")
                print_with_timestamp(f"ERROR: JSON parse error: {str(e)}")
                message.nack()
                return

            email_data = data.get('emailAddress')
            if not email_data:
                logger.error("No email data in message")
                print_with_timestamp("ERROR: No email data in message")
                message.nack()
                return

            # Fetch the latest message from the inbox
            print_with_timestamp("Fetching latest messages from inbox")
            results = service.users().messages().list(userId='me', labelIds=['INBOX'], maxResults=1).execute()
            messages = results.get('messages', [])

            if not messages:
                logger.info("No new messages found")
                print_with_timestamp("No new messages found in inbox")
                message.ack()
                return

            # Process only the newest message
            msg_id = messages[0]['id']
            print_with_timestamp(f"Processing newest message with ID: {msg_id}")
            result = process_email_message(service, msg_id)
            logger.info(f"Processed email: {result.get('subject', 'Unknown')}")
            print_with_timestamp(f"Processed email: {result.get('subject', 'Unknown')}")
            message.ack()
            print_with_timestamp("Message acknowledged")
        except Exception as e:
            logger.error(f"Unexpected error in callback: {str(e)}")
            print_with_timestamp(f"ERROR: Unexpected error in callback: {str(e)}")
            import traceback
            print_with_timestamp(f"Traceback: {traceback.format_exc()}")
            message.nack()
            print_with_timestamp("Message not acknowledged due to error")

    try:
        print_with_timestamp(f"Subscribing to {subscription_path}")
        streaming_pull_future = subscriber.subscribe(subscription_path, callback=callback)
        logger.info(f"Listening for messages on {subscription_path}")
        print_with_timestamp(f"Listening for messages on {subscription_path}")
        print_with_timestamp("Waiting for messages... (Press Ctrl+C to exit)")
        streaming_pull_future.result()  # Blocks indefinitely
    except KeyboardInterrupt:
        print_with_timestamp("Received keyboard interrupt, shutting down...")
        streaming_pull_future.cancel()
        print_with_timestamp("Streaming pull cancelled")
    except Exception as e:
        if 'streaming_pull_future' in locals():
            streaming_pull_future.cancel()
            print_with_timestamp("Streaming pull cancelled due to error")
        logger.error(f"Subscription error: {str(e)}")
        print_with_timestamp(f"ERROR: Subscription error: {str(e)}")


# Main function
def main():
    """Initialize the application with Gmail API push notifications to Pub/Sub."""
    logger.info("Starting application")
    print_with_timestamp("=========================================")
    print_with_timestamp("Starting Gmail notification application")
    print_with_timestamp("=========================================")

    try:
        # Setup Gmail service
        print_with_timestamp("Getting Gmail service...")
        service = get_gmail_service()
        print_with_timestamp("Gmail service initialized successfully")

        # Setup Gmail watch
        print_with_timestamp("Setting up Gmail watch...")
        history_id = setup_watch(service)
        print_with_timestamp(f"Gmail watch setup complete with historyId: {history_id}")

        print_with_timestamp("Using direct Pub/Sub subscription")
        process_pubsub_message(service)

    except Exception as e:
        logger.error(f"Application initialization failed: {str(e)}")
        print_with_timestamp(f"ERROR: Application initialization failed: {str(e)}")
        import traceback
        print_with_timestamp(f"Traceback: {traceback.format_exc()}")
        raise


if __name__ == "__main__":
    print_with_timestamp("Script executed directly")
    main()