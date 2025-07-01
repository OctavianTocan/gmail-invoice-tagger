# GitHub Actions Hanging Issue - Analysis & Solutions

## Problem Identified

The GitHub Actions workflow is getting stuck at this line in `main.py`:

```python
creds = flow.run_local_server(port=0, open_browser=False)
```

### Root Cause
The `run_local_server()` method from Google's OAuth library is designed for **interactive authentication** where a user manually authorizes the application. In GitHub Actions (headless CI environment), this method:

1. Starts a local HTTP server waiting for OAuth callbacks
2. Hangs indefinitely since no user can complete the authorization flow
3. Never receives the callback from Google's OAuth service
4. Times out or runs until the GitHub Actions job limit (6 hours for free tier)

## Solutions

### Option 1: Service Account Authentication (Recommended)

Service accounts are designed for server-to-server authentication without user interaction.

#### Setup Steps:
1. **Create a Service Account** in Google Cloud Console
2. **Enable Gmail API** for the service account
3. **Generate and download** the service account key (JSON file)
4. **Store the JSON** as a GitHub Secret
5. **Modify the authentication code** to use service accounts

#### Code Changes:
```python
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build

def gmail_authenticate():
    """Authenticate using service account credentials."""
    try:
        # Load service account credentials from environment variable
        service_account_info = json.loads(os.getenv("GMAIL_SERVICE_ACCOUNT_KEY"))
        
        credentials = service_account.Credentials.from_service_account_info(
            service_account_info, 
            scopes=SCOPES
        )
        
        # For domain-wide delegation (if needed)
        # credentials = credentials.with_subject('user@yourdomain.com')
        
        service = build("gmail", "v1", credentials=credentials)
        return service
        
    except Exception as error:
        print(f"Authentication failed: {error}")
        return None
```

#### Requirements Update:
```txt
google-api-python-client
google-auth
google-genai
```

### Option 2: Pre-authorized Refresh Token

Use a refresh token obtained from a previous interactive OAuth session.

#### Setup Steps:
1. **Run OAuth flow locally** once to get refresh token
2. **Store refresh token** as GitHub Secret
3. **Modify code** to use stored refresh token

#### Code Changes:
```python
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

def gmail_authenticate():
    """Authenticate using stored refresh token."""
    try:
        client_config = json.loads(os.getenv("GMAIL_OAUTH_CLIENT_CONFIG"))
        refresh_token = os.getenv("GMAIL_REFRESH_TOKEN")
        
        credentials = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri=client_config['installed']['token_uri'],
            client_id=client_config['installed']['client_id'],
            client_secret=client_config['installed']['client_secret'],
            scopes=SCOPES
        )
        
        # Refresh the token
        credentials.refresh(Request())
        
        service = build("gmail", "v1", credentials=credentials)
        return service
        
    except Exception as error:
        print(f"Authentication failed: {error}")
        return None
```

### Option 3: Application Default Credentials

Use Google's Application Default Credentials (ADC) mechanism.

#### Setup Steps:
1. **Set up ADC** in the GitHub Actions environment
2. **Configure credentials** through environment variables

#### Code Changes:
```python
from google.auth import default

def gmail_authenticate():
    """Authenticate using Application Default Credentials."""
    try:
        credentials, project = default(scopes=SCOPES)
        service = build("gmail", "v1", credentials=credentials)
        return service
        
    except Exception as error:
        print(f"Authentication failed: {error}")
        return None
```

## Recommended Workflow Update

Update the GitHub Actions workflow to handle the new authentication method:

```yaml
name: Run main.py on schedule

on:
  schedule:
    - cron: '0 2 * * *'
  workflow_dispatch:

jobs:
  run-tagger:
    runs-on: ubuntu-latest
    timeout-minutes: 10  # Add timeout to prevent infinite hanging

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.x'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt

      - name: Run main.py
        run: |
          python main.py
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
          # Choose one based on selected solution:
          GMAIL_SERVICE_ACCOUNT_KEY: ${{ secrets.GMAIL_SERVICE_ACCOUNT_KEY }}  # Option 1
          # GMAIL_REFRESH_TOKEN: ${{ secrets.GMAIL_REFRESH_TOKEN }}            # Option 2
          # GMAIL_OAUTH_CLIENT_CONFIG: ${{ secrets.GMAIL_OAUTH_CLIENT_CONFIG }}  # Option 2
```

## Additional Improvements

1. **Add timeout**: Prevent jobs from running indefinitely
2. **Add error handling**: Better error messages for debugging
3. **Add logging**: Monitor authentication and API calls
4. **Test locally**: Verify authentication works before deploying

## Security Considerations

- Never commit credentials to the repository
- Use GitHub Secrets for all sensitive data
- Regularly rotate service account keys
- Follow principle of least privilege for API scopes

## Next Steps

1. Choose authentication method (Service Account recommended)
2. Set up credentials in Google Cloud Console
3. Update the code with new authentication method
4. Add GitHub Secrets for credentials
5. Test the workflow with `workflow_dispatch` trigger