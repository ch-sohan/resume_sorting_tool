import requests

def call_gemini_api(file_path):
    url = "https://gemini.api.endpoint"  # Replace with the actual Gemini API endpoint
    headers = {"Authorization": "Bearer YOUR_GEMINI_API_KEY"}
    files = {"file": open(file_path, "rb")}

    response = requests.post(url, headers=headers, files=files)
    if response.status_code == 200:
        return response.json()  # Extracted resume data
    else:
        return {"error": "Failed to process resume"}
