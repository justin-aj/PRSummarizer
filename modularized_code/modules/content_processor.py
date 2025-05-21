"""
Email content processing module for PR Summarizer application.
"""
import base64
import email
import logging
import re
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from utils.helpers import print_with_timestamp, resolve_urls

logger = logging.getLogger(__name__)


def parse_email_content(msg_data):
    """
    Parse email content from Gmail API message data.

    Args:
        msg_data (dict): Message data from Gmail API

    Returns:
        dict: Parsed email content with subject, timestamp, and HTML body
    """
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

    html_body = _extract_email_body(payload, mime_type, parts)

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


def _decode_body(data):
    """
    Decode base64 encoded email content.

    Args:
        data (str): Base64 encoded data

    Returns:
        str: Decoded content
    """
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


def _extract_html(parts):
    """
    Recursively extract HTML from email parts, preserving all HTML content including URLs.

    Args:
        parts (list): Email parts

    Returns:
        str: HTML content
    """
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
                html_content = _decode_body(body_data)
                print_with_timestamp(f"HTML content extracted, length: {len(html_content)}")
                return html_content
        elif part_type == 'text/plain':
            body_data = part.get('body', {}).get('data', '')
            if body_data:
                plain_content = _decode_body(body_data)
                print_with_timestamp(f"Plain text content extracted, length: {len(plain_content)}")
        elif part_type.startswith('multipart') and 'parts' in part:
            print_with_timestamp(f"Found nested multipart, recursing into {len(part['parts'])} child parts")
            nested = _extract_html(part['parts'])
            if nested:
                return nested

    if plain_content and not html_content:
        print_with_timestamp("Converting plain text to HTML")
        return f"<pre>{plain_content}</pre>"

    print_with_timestamp("No HTML content found in any parts")
    return ''


def _extract_email_body(payload, mime_type, parts):
    """
    Extract email body based on mime type.

    Args:
        payload (dict): Email payload
        mime_type (str): MIME type of the email
        parts (list): Email parts

    Returns:
        str: HTML body
    """
    html_body = ''

    if mime_type.startswith('multipart'):
        print_with_timestamp("Processing multipart email")
        html_body = _extract_html(parts)
    elif mime_type == 'text/html':
        print_with_timestamp("Processing HTML email")
        body_data = payload.get('body', {}).get('data', '')
        if body_data:
            html_body = _decode_body(body_data)
            print_with_timestamp(f"Direct HTML body extracted, length: {len(html_body)}")
        else:
            print_with_timestamp("No body data found in HTML email")
    elif mime_type == 'text/plain':
        print_with_timestamp("Processing plain text email")
        body_data = payload.get('body', {}).get('data', '')
        if body_data:
            plain_text = _decode_body(body_data)
            html_body = f"<pre>{plain_text}</pre>"
            print_with_timestamp(f"Converted plain text to HTML, length: {len(html_body)}")
        else:
            print_with_timestamp("No body data found in plain text email")
    else:
        print_with_timestamp(f"Unhandled MIME type: {mime_type}")
        body_data = payload.get('body', {}).get('data', '')
        if body_data:
            html_body = _decode_body(body_data)
            print_with_timestamp(f"Extracted content from unknown MIME type, length: {len(html_body)}")

    return html_body


def get_email_sender(msg_data):
    """
    Extract sender from email headers.

    Args:
        msg_data (dict): Message data from Gmail API

    Returns:
        str: Email sender
    """
    headers = msg_data['payload'].get('headers', [])
    return next((h['value'] for h in headers if h['name'].lower() in ['from', 'sender']), '')


def process_html_content(html):
    """
    Process HTML content to extract body text and URLs.

    Args:
        html (str): HTML content

    Returns:
        tuple: (body text, list of resolved URLs)
    """
    logger.info("Processing HTML content")
    print_with_timestamp("Processing HTML content")

    try:
        soup = BeautifulSoup(html, 'html.parser')

        # Remove non-content tags
        for tag in soup(['script', 'style', 'nav', 'footer', 'header']):
            tag.decompose()

        # Extract URLs from anchor tags
        urls = [a.get('href') for a in soup.find_all('a', href=True)]

        # Get body text (limited to 1000 chars)
        body = ' '.join(soup.stripped_strings)[:1000]

        # Extract URLs from text
        text_urls = re.findall(r'https?://\S+', soup.get_text())

        # Combine and deduplicate URLs
        all_urls = list(set(urls + text_urls))

        # Resolve any redirects
        final_urls = resolve_urls(all_urls)

        return body, final_urls
    except Exception as e:
        logger.error(f"Error processing HTML: {str(e)}")
        print_with_timestamp(f"ERROR: Error processing HTML: {str(e)}")
        return "", []