"""
Gmail API client module for PR Summarizer application.
"""
import os
import pickle
import logging
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import config
from utils.helpers import print_with_timestamp

logger = logging.getLogger(__name__)


def get_gmail_service():
    """
    Initialize Gmail API service with authentication.

    Returns:
        googleapiclient.discovery.Resource: Authenticated Gmail API service
    """
    logger.info("Initializing Gmail service")
    print_with_timestamp("Initializing Gmail service")

    creds = None
    if os.path.exists(config.TOKEN_PICKLE_PATH):
        print_with_timestamp(f"Found existing {config.TOKEN_PICKLE_PATH} file")
        with open(config.TOKEN_PICKLE_PATH, 'rb') as token:
            creds = pickle.load(token)
            print_with_timestamp(
                f"Loaded credentials from {config.TOKEN_PICKLE_PATH}, valid: {creds.valid if creds else False}")

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logger.info("Refreshing expired credentials")
            print_with_timestamp("Refreshing expired credentials")
            creds.refresh(Request())
            print_with_timestamp("Credentials refreshed successfully")
        else:
            logger.info("Creating new credentials flow")
            print_with_timestamp(f"Creating new credentials flow with client secrets file {config.CREDENTIALS_PATH}")
            flow = InstalledAppFlow.from_client_secrets_file(config.CREDENTIALS_PATH, config.SCOPES)
            print_with_timestamp("Starting local server flow for authentication")
            creds = flow.run_local_server(port=0)
            print_with_timestamp("Authentication flow completed successfully")

        with open(config.TOKEN_PICKLE_PATH, 'wb') as token:
            pickle.dump(creds, token)
            logger.info(f"Saved new credentials to {config.TOKEN_PICKLE_PATH}")
            print_with_timestamp(f"Saved new credentials to {config.TOKEN_PICKLE_PATH}")

    print_with_timestamp("Building Gmail API service")
    service = build('gmail', 'v1', credentials=creds)
    logger.info("Gmail service initialized successfully")
    print_with_timestamp("Gmail service initialized successfully")

    return service


def setup_watch(service):
    """
    Set up Gmail API push notifications to Pub/Sub.

    Args:
        service (googleapiclient.discovery.Resource): Gmail API service

    Returns:
        str: History ID from Gmail API watch response
    """
    logger.info("Setting up Gmail watch")
    print_with_timestamp("Setting up Gmail watch")

    # Watch request
    request = {
        'labelIds': ['INBOX'],
        'topicName': f'projects/{config.PROJECT_ID}/topics/{config.TOPIC_NAME}'
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