"""
Helper utilities for PR Summarizer application.
"""
import requests
from datetime import datetime


def print_with_timestamp(message):
    """
    Print a message with a timestamp for better debugging.

    Args:
        message (str): Message to print
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-2]
    print(f"[{timestamp}] {message}")


def resolve_urls(url_list):
    """
    Resolve redirects to get final URLs.

    Args:
        url_list (list): List of URLs to resolve

    Returns:
        list: List of resolved URLs
    """
    resolved_urls = []
    for url in url_list:
        try:
            response = requests.get(url, allow_redirects=True, timeout=5)
            resolved_urls.append(response.url)
        except requests.exceptions.RequestException as e:
            resolved_urls.append(f"Error: {e}")
    return resolved_urls