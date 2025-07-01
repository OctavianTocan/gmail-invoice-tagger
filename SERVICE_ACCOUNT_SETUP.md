# Service Account Setup Guide

This guide will help you set up service account authentication for your Gmail email classifier to work with GitHub Actions.

## Prerequisites

- Google Cloud Project with Gmail API enabled
- GitHub repository with Actions enabled
- Admin access to the Google Workspace (if using domain-wide delegation)

## Step 1: Create a Service Account

1. **Go to Google Cloud Console**
   - Navigate to [Google Cloud Console](https://console.cloud.google.com/)
   - Select your project (or create a new one)

2. **Enable Gmail API**
   - Go to "APIs & Services" > "Library"
   - Search for "Gmail API"
   - Click "Enable"

3. **Create Service Account**
   - Go to "IAM & Admin" > "Service Accounts"
   - Click "Create Service Account"
   - Enter a name (e.g., "gmail-email-classifier")
   - Add description: "Service account for automated email classification"
   - Click "Create and Continue"

4. **Skip Role Assignment** (for now)
   - Click "Continue" without adding roles
   - Click "Done"

## Step 2: Generate Service Account Key

1. **Find your service account** in the list
2. **Click on the email address** to open details
3. **Go to "Keys" tab**
4. **Click "Add Key" > "Create new key"**
5. **Select "JSON" format**
6. **Click "Create"**
7. **Download and save the JSON file securely**

## Step 3: Configure Domain-Wide Delegation (Required for Gmail Access)

Since Gmail API requires accessing user data, you need to set up domain-wide delegation:

1. **Enable Domain-Wide Delegation**
   - In your service account details, check "Enable Google Workspace Domain-wide Delegation"
   - Enter a product name (e.g., "Email Classifier")
   - Click "Save"

2. **Note the Client ID**
   - Copy the "Client ID" from your service account details
   - You'll need this for the next step

3. **Configure in Google Workspace Admin Console**
   - Go to [Google Admin Console](https://admin.google.com/)
   - Navigate to "Security" > "Access and data control" > "API controls"
   - Click "Manage Domain Wide Delegation"
   - Click "Add new"
   - Enter the Client ID from step 2
   - Enter OAuth scopes: `https://www.googleapis.com/auth/gmail.modify`
   - Click "Authorize"

## Step 4: Update Code for Domain-Wide Delegation

In your `main.py`, you need to specify which user's Gmail account to access. Uncomment and modify this line in the `gmail_authenticate()` function:

```python
credentials = credentials.with_subject(subject_email)
```

## Step 5: Add GitHub Secrets

1. **Go to your GitHub repository**
2. **Navigate to Settings > Secrets and variables > Actions**
3. **Add the following secrets:**

   - **Name**: `GMAIL_SERVICE_ACCOUNT_KEY`
   - **Value**: The entire contents of the JSON file you downloaded in Step 2
   
   - **Name**: `GEMINI_API_KEY` (if not already added)
   - **Value**: Your Google Gemini API key

## Step 6: Test the Setup

1. **Trigger the workflow manually**
   - Go to "Actions" tab in your GitHub repository
   - Select your workflow
   - Click "Run workflow"

2. **Check the logs**
   - Look for "Successfully authenticated with Gmail API using service account"
   - Verify that emails are being processed

## Troubleshooting

### Common Issues:

1. **"Service account does not have domain-wide delegation enabled"**
   - Ensure you completed Step 3 correctly
   - Verify the Client ID matches in both places

2. **"Insufficient Permission" or "Access denied"**
   - Check that domain-wide delegation is properly configured
   - Verify the OAuth scopes are correct
   - Ensure the subject email is valid

3. **"Invalid service account key"**
   - Verify the JSON key is copied completely to GitHub Secrets
   - Check for any formatting issues or extra spaces

4. **Authentication still failing**
   - Double-check that Gmail API is enabled in your Google Cloud project
   - Verify the service account email has the correct permissions

### Debugging Tips:

- Add logging to see what's happening:
  ```python
  print(f"Service account email: {service_account_info.get('client_email')}")
  print(f"Project ID: {service_account_info.get('project_id')}")
  ```

- Test authentication locally first before deploying to GitHub Actions

## Security Notes

- **Never commit the service account key to your repository**
- **Regularly rotate service account keys** (recommended every 90 days)
- **Use the principle of least privilege** - only grant necessary permissions
- **Monitor service account usage** in Google Cloud Console

## Alternative: Personal Gmail Account

If you're using a personal Gmail account (not Google Workspace), you'll need to use the refresh token approach instead. Service accounts with domain-wide delegation only work with Google Workspace domains.

For personal accounts, refer to Option 2 in the `github_actions_fix_analysis.md` file.