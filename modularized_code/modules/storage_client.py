"""
Google Cloud Storage client module for PR Summarizer application.
"""
import json
import logging
from google.cloud import storage
import config
from utils.helpers import print_with_timestamp

logger = logging.getLogger(__name__)


def save_to_gcs(data, filename):
    """
    Save data to Google Cloud Storage.

    Args:
        data: Data to save (dict or string)
        filename (str): Filename to save as

    Returns:
        bool: True if save was successful, False otherwise
    """
    logger.info(f"Saving to GCS: {filename}")
    print_with_timestamp(f"Saving to GCS: {filename}")

    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(config.BUCKET_NAME)
        blob = bucket.blob(config.RESULTS_PREFIX + filename)

        if isinstance(data, dict):
            data = json.dumps(data, indent=2)
            print_with_timestamp(f"Converted dict to JSON string, length: {len(data)}")

        print_with_timestamp(f"Uploading to gs://{config.BUCKET_NAME}/{config.RESULTS_PREFIX}{filename}")
        blob.upload_from_string(data, content_type="application/json")
        logger.info(f"Successfully saved to gs://{config.BUCKET_NAME}/{config.RESULTS_PREFIX}{filename}")
        print_with_timestamp(f"Successfully saved to gs://{config.BUCKET_NAME}/{config.RESULTS_PREFIX}{filename}")
        return True
    except Exception as e:
        logger.error(f"Failed to save to GCS: {str(e)}")
        print_with_timestamp(f"ERROR: Failed to save to GCS: {str(e)}")
        return False