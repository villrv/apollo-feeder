from google.assistant.library import Assistant
from google.assistant.library.event import EventType
import json
import os

def main():
    credentials = os.path.join(os.path.expanduser('~/.config'), 'google-oauthlib-tool', 'credentials.json')
    with open(credentials, 'r') as f:
        creds = json.load(f)

    with Assistant(creds) as assistant:
        assistant.send_text_query("Turn on the lights")

if __name__ == '__main__':
    main()
