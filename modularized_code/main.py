"""
Main application entry point for PR Summarizer.
"""
import json
import logging
import traceback
from datetime import datetime, timezone

import config
from logging_setup import setup_logging, print_with_timestamp
from modules.gmail_client import get_gmail_service, setup_watch
from modules.pubsub_client import initialize_pubsub, process_pubsub_messages
from modules.storage_client import save_to_gcs
from modules.ai_client import initialize_gemini, classify_press_release, summarize_press_release
from modules.content_processor import parse_email_content, process_html_content, get_email_sender
from modules.scraper import sync_scrape_url


def process_email_message(service, message_id):
    """
    Process a single email message.

    Args:
        service: Gmail API service
        message_id (str): Message ID

    Returns:
        dict: Processing result
    """
    logger.info(f"Processing email message: {message_id}")
    print_with_timestamp(f"Processing email message: {message_id}")

    try:
        print_with_timestamp(f"Fetching message data for ID: {message_id}")
        msg_data = service.users().messages().get(userId='me', id=message_id).execute()
        print_with_timestamp(f"Successfully fetched message data, snippet: {msg_data.get('snippet', '')[:50]}...")

        # Parse email content
        email_info = parse_email_content(msg_data)
        print_with_timestamp(f"Email parsed, subject: {email_info['subject']}")

        # Extract sender
        sender = get_email_sender(msg_data)
        print_with_timestamp(f"Email sender: {sender}")

        # Process HTML content
        body, urls = process_html_content(email_info['html'])
        print_with_timestamp(f"HTML processed, body length: {len(body)}, URLs count: {len(urls)}")

        # Classify email as press release
        print_with_timestamp("Classifying email")
        classification = classify_press_release(gemini_model, email_info['subject'], body, urls)
        print_with_timestamp(f"Classification result: {classification}")

        summary = {}
        press_release_text = None
        press_release_url = None
        press_release_website_timestamp = None

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
                summary = summarize_press_release(gemini_model, text)
                press_release_website_timestamp = summary.get('timestamp', '')
                logger.info(f"Generated summary: {summary.get('headline', '')}")
                print_with_timestamp(f"Generated summary: {summary.get('headline', '')}")
            else:
                print_with_timestamp("No text content available for summarization")
        else:
            print_with_timestamp("Email not classified as press release, skipping summarization")

        # Create result
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

        # Save to GCS
        filename = f"{message_id}.json"
        save_to_gcs(result, filename)

        logger.info(f"Completed processing email: {message_id}")
        print_with_timestamp(f"Completed processing email: {message_id}")
        return result

    except Exception as e:
        logger.error(f"Error processing email {message_id}: {str(e)}")
        print_with_timestamp(f"ERROR: Error processing email {message_id}: {str(e)}")
        print_with_timestamp(f"Traceback: {traceback.format_exc()}")
        return {}


def main():
    """
    Initialize the application with Gmail API push notifications to Pub/Sub.
    """
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

        # Start processing Pub/Sub messages
        print_with_timestamp("Using direct Pub/Sub subscription")
        pull_future = process_pubsub_messages(subscriber, service, process_email_message)

        # Wait for messages indefinitely
        pull_future.result()

    except KeyboardInterrupt:
        print_with_timestamp("Received keyboard interrupt, shutting down...")
        if 'pull_future' in locals():
            pull_future.cancel()
            print_with_timestamp("Streaming pull cancelled")

    except Exception as e:
        logger.error(f"Application initialization failed: {str(e)}")
        print_with_timestamp(f"ERROR: Application initialization failed: {str(e)}")
        print_with_timestamp(f"Traceback: {traceback.format_exc()}")
        raise


if __name__ == "__main__":
    # Setup logging
    logger, credentials = setup_logging()

    # Initialize Gemini
    gemini_model = initialize_gemini()

    # Initialize Pub/Sub
    publisher, subscriber, jwt_credentials = initialize_pubsub(credentials)

    print_with_timestamp("Script executed directly")
    main()