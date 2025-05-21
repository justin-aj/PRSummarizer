"""
Configuration module for PR Summarizer application.
"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Gmail API scopes
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly',
          'https://www.googleapis.com/auth/pubsub']

# Google Cloud settings
PROJECT_ID = os.getenv("PROJECT_ID", 'utilitarian-mix-459622-c9')
TOPIC_NAME = os.getenv("TOPIC_NAME", 'gmail-alerts')
SUBSCRIPTION_NAME = os.getenv("SUBSCRIPTION_NAME", 'gmail-alerts-sub')
BUCKET_NAME = os.getenv("BUCKET_NAME", "prsummarized-files")
RESULTS_PREFIX = "press-release-results/"

# Gemini settings
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = "models/gemini-2.0-flash"

# File paths
SERVICE_ACCOUNT_PATH = "pr-summarizer-key.json"
CREDENTIALS_PATH = "credentials.json"
TOKEN_PICKLE_PATH = "token.pickle"

# Pub/Sub settings
PUBSUB_AUDIENCE = "https://pubsub.googleapis.com/google.pubsub.v1.Subscriber"