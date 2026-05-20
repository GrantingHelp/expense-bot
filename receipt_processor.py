import anthropic
import base64
import os
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

def encode_image(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")

def process_receipt(image_path: str) -> dict:
    image_data = encode_image(image_path)

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": image_data,
                        },
                    },
                    {
                        "type": "text",
                        "text": """You are processing an expense receipt. Extract the following information and respond in this exact format:
VENDOR: <vendor name — short and clean, e.g. 'Shell', 'McDonald's', 'Marriott'. No parentheticals, no extra context, no location details>
DATE: <date in MM/DD/YYYY format>
AMOUNT: <total amount as a number, no $ sign>
CATEGORY: <one of: Fuel, Food, Tolls, Hotel, Other>
DESCRIPTION: <one concise sentence describing the purchase, e.g. 'Fuel purchase at Shell' or 'Lunch at McDonald's'>

If you cannot determine a field, write UNKNOWN for that field."""
                    }
                ],
            }
        ],
    )

    result = message.content[0].text
    parsed = {}
    for line in result.strip().split('\n'):
        if ':' in line:
            key, value = line.split(':', 1)
            parsed[key.strip()] = value.strip()

    return parsed