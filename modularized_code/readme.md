# Press Release Summarizer

The directory contains modularized code for better readability, maintainability, and collaboration. Each module handles a specific responsibility, making the codebase easier to understand, test, and extend while enabling multiple developers to work simultaneously on different components.

## Architecture

The application follows a modular architecture:

```
modularized_code/
├── main.py                     # Main application entry point
├── config.py                   # Configuration and environment variables
├── logging_setup.py            # Logging configuration
├── modules/
│   ├── __init__.py             # Initialize modules package
│   ├── gmail_client.py         # Gmail API operations
│   ├── scraper.py              # Web scraping operations
│   ├── pubsub_client.py        # Google Cloud Pub/Sub operations
│   ├── storage_client.py       # Google Cloud Storage operations
│   ├── ai_client.py            # Gemini AI operations
│   └── content_processor.py    # Email and text processing
└── utils/
    ├── __init__.py             # Initialize utils package
    └── helpers.py              # Helper functions
```

## Modules

### gmail_client.py
Handles Gmail API authentication and watching for new messages.

### scraper.py
Contains web scraping functionality with special handling for timestamp preservation.

### pubsub_client.py
Manages Google Cloud Pub/Sub topics, subscriptions, and message processing.

### storage_client.py
Provides Google Cloud Storage operations for saving results.

### ai_client.py
Interfaces with Google's Gemini AI for classification and summarization.

### content_processor.py
Processes email content, extracts relevant information, and prepares it for analysis.