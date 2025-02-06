import os
import pickle
import google.auth
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

SCOPES = ['https://www.googleapis.com/auth/calendar']


def authenticate_google():
    creds = None
    token_path = 'token.pkl'

    if os.path.exists(token_path):
        print("[INFO] Loading existing credentials...")
        with open(token_path, "rb") as token_file:
            creds = pickle.load(token_file)

    # Refresh expired credentials or authenticate new ones
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("[INFO] Refreshing expired token...")
            creds.refresh(Request())
        else:
            print("[INFO] Starting new authentication flow...")
            if not os.path.exists("client_secret_322286127811-5pjf7tm2kn4j8rb5i9ebjhrqehnj4dhk.apps.googleusercontent.com.json"):
                print("[ERROR] credentials.json file not found!")
                return None

            try:
                flow = InstalledAppFlow.from_client_secrets_file("client_secret_322286127811-5pjf7tm2kn4j8rb5i9ebjhrqehnj4dhk.apps.googleusercontent.com.json", SCOPES)
                creds = flow.run_local_server(port=0)
                print("[SUCCESS] Authentication successful!")

                # Save credentials for future use
                with open(token_path, "wb") as token_file:
                    pickle.dump(creds, token_file)
                print("[INFO] Token saved to token.pkl")

            except Exception as e:
                print(f"[ERROR] Authentication failed: {e}")
                return None

    return creds

if __name__ == "__main__":
    authenticate_google()