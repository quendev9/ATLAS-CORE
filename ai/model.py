import os

from dotenv import load_dotenv
from google import genai


load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise RuntimeError("GEMINI_API_KEY was not found in the .env file")


client = genai.Client(api_key=api_key)

chat = client.chats.create(
    model="gemini-3.6-flash"
)


def ask_gemini(message):
    response = chat.send_message(message)

    return response.text