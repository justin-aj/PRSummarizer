"""
Gemini AI client module for PR Summarizer application.
"""
import json
import logging
import google.generativeai as genai
import config
from utils.helpers import print_with_timestamp

logger = logging.getLogger(__name__)


def initialize_gemini():
    """
    Initialize Gemini API client.

    Returns:
        google.generativeai.GenerativeModel: Initialized Gemini model
    """
    print_with_timestamp("Configuring Gemini API")
    genai.configure(api_key=config.GEMINI_API_KEY)
    model = genai.GenerativeModel(config.GEMINI_MODEL)
    print_with_timestamp(f"Gemini API initialized with model: {config.GEMINI_MODEL}")
    return model


def construct_classification_prompt(subject, body, urls):
    """
    Construct a prompt for press release classification.

    Args:
        subject (str): Email subject
        body (str): Email body text
        urls (list): List of URLs found in the email

    Returns:
        str: Formatted prompt for Gemini
    """
    logger.debug(f"URLS found in email: {urls}")
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


def construct_summary_prompt(text):
    """
    Construct a prompt for press release summarization.

    Args:
        text (str): Press release text to summarize

    Returns:
        str: Formatted prompt for Gemini
    """
    return f"""
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


def call_gemini(model, prompt):
    """
    Call Gemini API with a prompt.

    Args:
        model: Initialized Gemini model
        prompt (str): Prompt to send to Gemini

    Returns:
        dict: Parsed JSON response or default response if error occurs
    """
    logger.info("Calling Gemini API")
    print_with_timestamp("Calling Gemini API")

    try:
        print_with_timestamp(f"Sending prompt to Gemini, length: {len(prompt)}")
        response = model.generate_content(prompt)
        print_with_timestamp(f"Received response from Gemini, text: {response.text[:100]}...")

        result = json.loads(response.text.strip())
        logger.info("Gemini API call successful")
        print_with_timestamp(f"Gemini API call successful, parsed JSON: {result}")
        return result
    except Exception as e:
        logger.error(f"Gemini API error: {str(e)}")
        print_with_timestamp(f"ERROR: Gemini API error: {str(e)}")
        return {"press_release": "NO", "type": None, "url": None, "text": None}


def classify_press_release(model, subject, body, urls):
    """
    Classify if an email is a press release.

    Args:
        model: Gemini model
        subject (str): Email subject
        body (str): Email body
        urls (list): URLs found in the email

    Returns:
        dict: Classification result
    """
    prompt = construct_classification_prompt(subject, body, urls)
    return call_gemini(model, prompt)


def summarize_press_release(model, text):
    """
    Generate a summary of a press release.

    Args:
        model: Gemini model
        text (str): Press release text

    Returns:
        dict: Summary result
    """
    logger.info("Generating summary")
    print_with_timestamp(f"Generating summary for text of length: {len(text)}")

    prompt = construct_summary_prompt(text)

    try:
        print_with_timestamp("Sending summarization prompt to Gemini")
        response = model.generate_content(prompt)
        print_with_timestamp(f"Received summarization response: {response.text[:100]}...")

        result = json.loads(response.text.strip())
        logger.info("Summary generated successfully")
        print_with_timestamp(f"Summary generated successfully: {result.get('headline', '')}")
        return result
    except Exception as e:
        logger.error(f"Summarization error: {str(e)}")
        print_with_timestamp(f"ERROR: Summarization error: {str(e)}")
        return {"headline": "", "key_result": "", "impacted_program": "", "next_step": ""}