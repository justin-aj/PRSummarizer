"""
Google Cloud Pub/Sub client module for PR Summarizer application.
"""
import json
import logging
import traceback
from google.cloud import pubsub_v1
from google.auth import jwt
import config
from utils.helpers import print_with_timestamp

logger = logging.getLogger(__name__)


def initialize_pubsub(credentials):
    """
    Initialize Pub/Sub client and ensure the topic exists.

    Args:
        credentials: Google Cloud credentials

    Returns:
        tuple: (publisher_client, subscriber_client, jwt_credentials)
    """
    print_with_timestamp("Initializing Pub/Sub clients")

    # Create JWT credentials for Pub/Sub
    jwt_credentials = jwt.Credentials.from_signing_credentials(
        credentials, audience=config.PUBSUB_AUDIENCE
    )
    print_with_timestamp("JWT credentials created for Pub/Sub")

    # Initialize publisher
    publisher = pubsub_v1.PublisherClient(credentials=credentials)
    topic_path = publisher.topic_path(config.PROJECT_ID, config.TOPIC_NAME)
    print_with_timestamp(f"Using Pub/Sub topic: {topic_path}")

    # Ensure topic exists
    try:
        publisher.get_topic(request={"topic": topic_path})
        logger.info(f"Topic {topic_path} already exists")
        print_with_timestamp(f"Topic {topic_path} already exists")
    except Exception as e:
        print_with_timestamp(f"Topic {topic_path} does not exist, creating it now: {str(e)}")
        publisher.create_topic(request={"name": topic_path})
        logger.info(f"Created topic {topic_path}")
        print_with_timestamp(f"Created topic {topic_path}")

    # Initialize subscriber
    subscriber = pubsub_v1.SubscriberClient(credentials=jwt_credentials)

    return publisher, subscriber, jwt_credentials


def process_pubsub_messages(subscriber, service, message_processor):
    """
    Subscribe to Pub/Sub and process incoming messages.

    Args:
        subscriber: Pub/Sub subscriber client
        service: Gmail API service
        message_processor: Function to process email messages
    """
    logger.info("Starting Pub/Sub message processing")
    print_with_timestamp("Starting Pub/Sub message processing")

    subscription_path = subscriber.subscription_path(config.PROJECT_ID, config.SUBSCRIPTION_NAME)
    print_with_timestamp(f"Using subscription: {subscription_path}")

    def callback(message):
        """
        Process incoming Pub/Sub messages.

        Args:
            message: Pub/Sub message
        """
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
            result = message_processor(service, msg_id)
            logger.info(f"Processed email: {result.get('email_subject', 'Unknown')}")
            print_with_timestamp(f"Processed email: {result.get('email_subject', 'Unknown')}")
            message.ack()
            print_with_timestamp("Message acknowledged")

        except Exception as e:
            logger.error(f"Unexpected error in callback: {str(e)}")
            print_with_timestamp(f"ERROR: Unexpected error in callback: {str(e)}")
            print_with_timestamp(f"Traceback: {traceback.format_exc()}")
            message.nack()
            print_with_timestamp("Message not acknowledged due to error")

    try:
        print_with_timestamp(f"Subscribing to {subscription_path}")
        streaming_pull_future = subscriber.subscribe(subscription_path, callback=callback)
        logger.info(f"Listening for messages on {subscription_path}")
        print_with_timestamp(f"Listening for messages on {subscription_path}")
        print_with_timestamp("Waiting for messages... (Press Ctrl+C to exit)")

        # Return the future so it can be managed by the caller
        return streaming_pull_future

    except Exception as e:
        logger.error(f"Subscription error: {str(e)}")
        print_with_timestamp(f"ERROR: Subscription error: {str(e)}")
        raise