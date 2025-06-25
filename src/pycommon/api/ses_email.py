# Copyright (c) 2024 Vanderbilt University
# Authors: Jules White, Allen Karns, Karely Rodriguez, Max Moundas

import json
import os

import requests


def send_email(
    access_token: str, email_to: str, email_subject: str, email_body: str
) -> bool:
    """
    Send an email using Amazon SES (Simple Email Service).

    Args:
        access_token: Bearer token for authentication
        email_to: Recipient email address
        email_subject: Subject line of the email
        email_body: Body content of the email

    Returns:
        bool: True if email was sent successfully, False otherwise
    """
    print("Initiate email call")

    endpoint = os.environ["API_BASE_URL"] + "/ses/send-email"

    request = {
        "data": {
            "email_to": email_to,
            "email_subject": email_subject,
            "email_body": email_body,
        }
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
    }

    try:
        response = requests.post(endpoint, headers=headers, data=json.dumps(request))
        print("Response: ", response.content)
        response_content = (
            response.json()
        )  # to adhere to object access return response dict

        if response.status_code == 200 and response_content.get("success", False):
            return True

    except Exception as e:
        print(f"Error sending email: {e}")

    return False
