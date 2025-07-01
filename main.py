import os
import pickle
import base64
import json
from typing import List, Dict

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2 import service_account
from google import genai
from google.genai import types

# ==============================================================================
# 1) CONFIGURATION & AUTHENTICATION SETUP
# ==============================================================================

# Define the scope of access needed for the Gmail API.
# 'modify' allows reading, composing, sending, and moving messages.
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

# Define the categories for classifying emails.
CATEGORIES = ["Orders", "Invoices", "Other"]

try:
    subject_email = os.getenv("GMAIL_SUBJECT_EMAIL")  
except KeyError:
    print("Error: GMAIL_SUBJECT_EMAIL environment variable not set.")
    exit()

# Initialize the Generative AI client
# Make sure your GEMINI_API_KEY is set as an environment variable.
try:
    # Using Google Gemini API.
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
except KeyError:
    print("Error: GEMINI_API_KEY environment variable not set.")
    exit()

def gmail_authenticate():
    """
    Authenticates with the Gmail API using service account credentials.
    
    This method is designed for server-to-server authentication and works
    well in automated environments like GitHub Actions.
    
    Returns:
        A Google API client service object for interacting with Gmail.
    """
    try:
        # Load service account credentials from environment variable
        service_account_key = os.getenv("GMAIL_SERVICE_ACCOUNT_KEY")
        if not service_account_key:
            print("Error: GMAIL_SERVICE_ACCOUNT_KEY environment variable not set.")
            print("Please store your service account JSON key in this variable.")
            return None
            
        service_account_info = json.loads(service_account_key)
        
        # Create credentials from service account info
        credentials = service_account.Credentials.from_service_account_info(
            service_account_info, 
            scopes=SCOPES
        )
        
        # For domain-wide delegation, uncomment and modify the following line:
        if subject_email:
            credentials = credentials.with_subject(subject_email)
        
        # Build and return the Gmail service object
        service = build("gmail", "v1", credentials=credentials)
        print("Successfully authenticated with Gmail API using service account.")
        return service
        
    except json.JSONDecodeError:
        print("Error: Could not decode the JSON in GMAIL_SERVICE_ACCOUNT_KEY.")
        print("Please ensure the service account key is valid JSON.")
        return None
    except Exception as error:
        print(f"Authentication failed: {error}")
        return None

# ==============================================================================
# 2) GMAIL API INTERACTIONS
# ==============================================================================

def fetch_unread_message_ids(service) -> List[Dict]:
    """
    Fetches a list of unread message IDs from the user's Gmail account.
    
    Args:
        service: The authenticated Gmail API service object.
        
    Returns:
        A list of message objects, or an empty list if no unread messages are found.
    """
    try:
        response = service.users().messages().list(
            userId="me", q="is:unread", maxResults=10
        ).execute()
        return response.get("messages", [])
    except HttpError as error:
        print(f"An error occurred while fetching messages: {error}")
        return []

def get_message_text(service, msg_id: str) -> str:
    """
    Retrieves the plain text content of a specific email.
    
    Args:
        service: The authenticated Gmail API service object.
        msg_id: The ID of the message to retrieve.
        
    Returns:
        The plain text body of the email as a string.
    """
    try:
        msg = service.users().messages().get(
            userId="me", id=msg_id, format="full"
        ).execute()
        
        parts = msg.get("payload", {}).get("parts", [])
        text_content = ""
        
        if not parts: # Handle simple, non-multipart emails
            body_data = msg.get("payload", {}).get("body", {}).get("data")
            if body_data:
                 text_content = base64.urlsafe_b64decode(body_data).decode("utf-8")
        else: # Handle multipart emails
            for part in parts:
                if part.get("mimeType") == "text/plain":
                    data = part.get("body", {}).get("data", "")
                    text_content += base64.urlsafe_b64decode(data).decode("utf-8")
                    
        return text_content
    except HttpError as error:
        print(f"An error occurred while getting message text: {error}")
        return ""

def get_or_create_label(service, label_name: str) -> str:
    """
    Gets the ID of an existing label or creates it if it doesn't exist.
    
    Args:
        service: The authenticated Gmail API service object.
        label_name: The name of the label to find or create.
        
    Returns:
        The ID of the label.
    """
    try:
        labels_response = service.users().labels().list(userId="me").execute()
        labels = labels_response.get("labels", [])
        
        for label in labels:
            if label["name"] == label_name:
                return label["id"]
        
        # If the label was not found, create it.
        new_label = {
            "name": label_name,
            "labelListVisibility": "labelShow",
            "messageListVisibility": "show",
        }
        created_label = service.users().labels().create(
            userId="me", body=new_label
        ).execute()
        return created_label["id"]
    except HttpError as error:
        print(f"An error occurred while processing labels: {error}")
        return ""

def apply_label(service, msg_id: str, label_id: str):
    """
    Applies a label to a message and marks it as read.
    
    Args:
        service: The authenticated Gmail API service object.
        msg_id: The ID of the message to modify.
        label_id: The ID of the label to add.
    """
    try:
        mods = {"addLabelIds": [label_id], "removeLabelIds": ["UNREAD"]}
        service.users().messages().modify(
            userId="me", id=msg_id, body=mods
        ).execute()
    except HttpError as error:
        print(f"An error occurred while applying the label: {error}")

# ==============================================================================
# 3) AI-POWERED CLASSIFICATION
# ==============================================================================

def classify_email(text: str) -> str:
    """
    Uses a generative AI model to classify email text into a category.
    
    Args:
        text: The email content to classify.
        
    Returns:
        The predicted category as a string (e.g., "Orders", "Other").
    """
    if not text:
        return "Other"

    prompt = (
        "Classify this email into one of the following categories: "
        f"{', '.join(CATEGORIES)}. Email text: '{text}'. "
    )
    
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash-lite-preview-06-17", 
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction="Respond with a single JSON object like {\"category\": \"...\"}."),
        )
        
        # The API should return valid JSON because of response_mime_type
        output = response.text
        category = response.text
        
        if category in CATEGORIES:
            return category
            
    except Exception as e:
        print(f"An error occurred during AI classification: {e}")
        
    return "Other"

# ==============================================================================
# 4) MAIN WORKFLOW
# ==============================================================================

def main():
    """
    Main function to run the email classification and labeling workflow.
    """
    print("Starting email classification process...")
    service = gmail_authenticate()
    
    if not service:
        print("Could not authenticate with Gmail. Exiting.")
        return

    messages = fetch_unread_message_ids(service)
    if not messages:
        print("No unread messages found.")
        return

    print(f"Found {len(messages)} unread emails. Processing...")
    for msg_summary in messages:
        msg_id = msg_summary["id"]
        text = get_message_text(service, msg_id)
        
        if not text:
            print(f"Msg {msg_id}: Could not retrieve text, skipping.")
            continue
            
        category = classify_email(text)
        print(f"Msg {msg_id}: Classified as '{category}'")
        
        label_id = get_or_create_label(service, category)
        if label_id:
            apply_label(service, msg_id, label_id)
            print(f"Msg {msg_id}: Successfully labeled and marked as read.")
    
    print("Processing complete.")

if __name__ == "__main__":
    main()

