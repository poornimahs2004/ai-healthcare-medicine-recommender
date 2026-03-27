import os
import requests
from dotenv import load_dotenv

# Load your API Key
load_dotenv()
API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()

print(f"--- Checking Available Models for your API Key ---")

if not API_KEY:
    print("❌ Error: API Key not found in .env file.")
else:
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={API_KEY}"
    
    try:
        response = requests.get(url)
        
        if response.status_code == 200:
            data = response.json()
            print("\n✅ SUCCESS! Found these available models:\n")
            found_vision = False
            for model in data.get('models', []):
                print(f"  • {model['name']}")
                if 'vision' in model['name'] or 'flash' in model['name']:
                    found_vision = True
            
            if not found_vision:
                print("\n⚠️  WARNING: No 'Flash' or 'Vision' models found. Image analysis might not work.")
        else:
            print(f"\n❌ Error accessing Google API: {response.status_code}")
            print(response.text)

    except Exception as e:
        print(f"\n❌ Connection Error: {e}")