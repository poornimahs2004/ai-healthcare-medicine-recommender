# test_key.py
import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
api_key = os.environ.get("GEMINI_API_KEY")

print(f"Key found: {api_key[:5]}..." if api_key else "NO KEY FOUND")

if api_key:
    genai.configure(api_key=api_key)
    try:
        print("Listing models...")
        for m in genai.list_models():
            print(f" - {m.name}")
        print("SUCCESS! Key is working.")
    except Exception as e:
        print(f"FAILED: {e}")