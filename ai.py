import requests
import sys

prompt = " ".join(sys.argv[1:])

response = requests.post(
    "http://127.0.0.1:5000/chat",
    json={
        "prompt": prompt
    }
)

print(response.json()["response"])