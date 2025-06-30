import os
import pickle
import base64
import json
from typing import List, Dict

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google_auth_oauthlib.flow import InstalledAppFlow

from genai import client as genai_client

# 1) CONFIG & AUTH SETUP
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
TOKEN_PICKLE = "token.pickle"     # stores Gmail access/refresh tokens

# categories you care about
CATEGORIES = ["Orders", "Invoices", "Other"]

# initialize GenAI
genai = genai_client.Client()
genai.set_api_key(os.environ["GENAI_API_KEY"])

def gmail_authenticate():
    # 1) load the raw JSON OAuth client config from an ENV var
    clientconfig = json.loads(os.environ["GMAIL_OAUTH_CLIENT_CONFIG"])
    
    # 2) spin up the flow directly from that dict
    flow = InstalledAppFlow.fromclientconfig(client_config, SCOPES)
    creds = flow.runlocalserver(port=0)
    
    # 3) build your Gmail service
    return build("gmail", "v1", credentials=creds)

# 2) FETCH UNREAD EMAIL IDS
def fetch_unread_message_ids(service) -> List[str]:
    resp = service.users().messages().list(userId="me", q="is:unread", maxResults=10).execute()
    return resp.get("messages", [])

# 3) GET & PARSE MESSAGE TEXT
def get_message_text(service, msg_id: str) -> str:
    msg = service.users().messages().get(userId="me", id=msg_id, format="full").execute()
    parts = msg["payload"].get("parts", [])
    text = ""
    for part in parts:
        if part["mimeType"] == "text/plain":
            data = part["body"]["data"]
            text += base64.urlsafe_b64decode(data).decode("utf-8")
    return text

# 4) CALL GEMINI TO CLASSIFY
def classify_email(text: str) -> str:
    prompt = (
        "Classify this email into one of these categories: "
        + ", ".join(CATEGORIES)
        + ".

Email:
"
        + text
        + "

Respond with a single JSON object like {\"category\": \"...\"}."
    )
    resp = genai.chat.completions.create(
        model="models/gemini-2.5-flash-lite-preview-06-17",
        messages=[{"author": "user", "content": prompt}]
    )
    content = resp.choices[0].message.content
    try:
        out = json.loads(content)
        if out.get("category") in CATEGORIES:
            return out["category"]
    except json.JSONDecodeError:
        pass
    return "Other"

# 5) ENSURE LABEL EXISTS & APPLY IT
def get_or_create_label(service, label_name: str) -> str:
    labels = service.users().labels().list(userId="me").execute().get("labels", [])
    for l in labels:
        if l["name"] == label_name:
            return l["id"]
    # if not found, create it
    label = {
        "name": label_name,
        "labelListVisibility": "labelShow",
        "messageListVisibility": "show",
    }
    created = service.users().labels().create(userId="me", body=label).execute()
    return created["id"]

def apply_label(service, msg_id: str, label_id: str):
    mods = {"addLabelIds": [label_id], "removeLabelIds": ["UNREAD"]}
    service.users().messages().modify(userId="me", id=msg_id, body=mods).execute()

# 6) MAIN WORKFLOW
def main():
    service = gmail_authenticate()
    for msg in fetch_unread_message_ids(service):
        mid = msg["id"]
        text = get_message_text(service, mid)
        category = classify_email(text)
        label_id = get_or_create_label(service, category)
        apply_label(service, mid, label_id)
        print(f"Msg {mid}: → {category}")
        
if __name__ == "__main__":
    main()
