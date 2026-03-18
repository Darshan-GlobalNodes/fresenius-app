"""
Example: HTTP Client for Fresenius AI Assistant API

Use this to call the Lambda function via API Gateway HTTP endpoint
from any application (doesn't require AWS SDK)
"""

import requests
import json


class FreseniusAPIClient:
    """HTTP client for Fresenius AI Assistant API"""

    def __init__(self, api_url, jwt_token=None):
        """
        Initialize the client

        Args:
            api_url: API Gateway URL (e.g., https://abc123.execute-api.us-east-1.amazonaws.com)
            jwt_token: Optional JWT token for authenticated requests
        """
        self.api_url = api_url.rstrip('/')
        self.jwt_token = jwt_token
        self.session = requests.Session()

        if jwt_token:
            self.session.cookies.set('access_token', jwt_token)

    def get_config(self):
        """Get API configuration"""
        response = self.session.get(f"{self.api_url}/api/config")
        response.raise_for_status()
        return response.json()

    def get_user(self):
        """Get current user information"""
        response = self.session.get(f"{self.api_url}/api/user")
        response.raise_for_status()
        return response.json()

    def update_aws_credentials(self, access_key_id, secret_access_key, session_token):
        """
        Update AWS credentials for Bedrock access

        Args:
            access_key_id: AWS access key ID
            secret_access_key: AWS secret access key
            session_token: AWS session token
        """
        response = self.session.post(
            f"{self.api_url}/api/aws-credentials",
            json={
                'access_key_id': access_key_id,
                'secret_access_key': secret_access_key,
                'session_token': session_token
            }
        )
        response.raise_for_status()
        return response.json()

    def check_credentials_status(self):
        """Check if AWS credentials are currently set"""
        response = self.session.get(f"{self.api_url}/api/aws-credentials/status")
        response.raise_for_status()
        return response.json()


# Example usage
def main():
    # Replace with your API Gateway URL and JWT token
    API_URL = "https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com"
    JWT_TOKEN = "your_jwt_token_here"

    client = FreseniusAPIClient(API_URL, JWT_TOKEN)

    try:
        # Get configuration
        print("Getting API configuration...")
        config = client.get_config()
        print("Config:", config)

        # Get user info
        print("\nGetting user info...")
        user = client.get_user()
        print("User:", user)

        # Check credentials status
        print("\nChecking credentials status...")
        status = client.check_credentials_status()
        print("Status:", status)

        # Update credentials (example)
        # print("\nUpdating AWS credentials...")
        # result = client.update_aws_credentials(
        #     access_key_id="ASIA...",
        #     secret_access_key="secret...",
        #     session_token="token..."
        # )
        # print("Update result:", result)

    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error: {e}")
        print(f"Response: {e.response.text}")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == '__main__':
    main()