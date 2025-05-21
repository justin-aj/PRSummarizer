"""
Logging configuration for PR Summarizer application.
"""
import logging
from datetime import datetime
from google.cloud import logging as cloud_logging
from google.cloud.logging_v2.handlers import CloudLoggingHandler
from google.oauth2 import service_account
import config


def print_with_timestamp(message):
    """
    Print a message with a timestamp for better debugging.

    Args:
        message (str): Message to print
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-2]
    print(f"[{timestamp}] {message}")


def setup_logging():
    """
    Set up logging with Google Cloud Logging and console output.

    Returns:
        logging.Logger: Configured logger
    """
    print_with_timestamp("Setting up Google Cloud Logging client")

    # Google Cloud Logging client with service account credentials
    credentials = service_account.Credentials.from_service_account_file(config.SERVICE_ACCOUNT_PATH)
    cloud_client = cloud_logging.Client(credentials=credentials, project=config.PROJECT_ID)

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

    return logger, credentials