import os
import shutil
import tempfile
import zipfile
import json
import requests
from pathlib import Path
import pandas as pd
import csv
from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import traceback

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# AI Proxy configuration - corrected according to documentation
AIPROXY_BASE_URL = "https://aiproxy.sanand.workers.dev/openai"
AIPROXY_TOKEN = os.environ.get("AIPROXY_TOKEN")

@app.post("/api/")
async def process_question(
    question: str = Form(...),
    file: UploadFile = File(None)
):
    try:
        print(f"Received request with question: '{question}'")
        if not AIPROXY_TOKEN:
            print("WARNING: AIPROXY_TOKEN environment variable not set!")
            return {"answer": "Error: AIPROXY_TOKEN not configured"}
        
        temp_dir = tempfile.mkdtemp()
        file_paths = []
        file_contents = {}

        try:
            if file and file.filename:
                print(f"Processing file: {file.filename}")
                file_path = os.path.join(temp_dir, file.filename)

                with open(file_path, "wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)

                file_paths.append(file_path)

                if file.filename.endswith('.zip'):
                    extract_dir = os.path.join(temp_dir, "extracted")
                    os.makedirs(extract_dir, exist_ok=True)

                    with zipfile.ZipFile(file_path, 'r') as zip_ref:
                        zip_ref.extractall(extract_dir)

                    for root, _, files in os.walk(extract_dir):
                        for extracted_file in files:
                            extracted_path = os.path.join(root, extracted_file)
                            file_paths.append(extracted_path)

                            if extracted_file.endswith('.csv'):
                                try:
                                    df = pd.read_csv(extracted_path)
                                    if "answer" in df.columns:
                                        file_contents[extracted_file] = df['answer'].tolist()
                                except Exception as e:
                                    file_contents[extracted_file] = f"Error reading CSV: {str(e)}"

            # Special handling for test questions
            if question.lower() == "test":
                return {"answer": "This is a test response that bypasses the AI Proxy."}

            answer = await generate_answer(question, file_contents)
            print(f"Generated answer: '{answer[:50]}...'")  # Only print first 50 chars for privacy
            return {"answer": answer}
        finally:
            # Clean up temp directory
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
                
    except Exception as e:
        print(f"ERROR in process_question: {str(e)}")
        print(traceback.format_exc())
        return {"answer": f"Server error: {str(e)}"}


async def generate_answer(question: str, file_contents: dict = None):
    try:
        # Prepare the content with file contents if available
        content = f"Answer this question directly and concisely: {question}\n"
        
        if file_contents:
            content += "File contents:\n"
            for filename, data in file_contents.items():
                content += f"--- {filename} ---\n{data}\n\n"
        
        content += "Return ONLY the answer value, nothing else. No explanations."
        
        # Make the API call using the correct OpenAI-compatible format
        url = f"{AIPROXY_BASE_URL}/v1/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {AIPROXY_TOKEN}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "You are a helpful assistant that answers questions directly and concisely."},
                {"role": "user", "content": content}
            ]
        }
        
        print(f"Sending request to AI Proxy at {url} with token: {AIPROXY_TOKEN[:5]}...")
        
        response = requests.post(url, headers=headers, json=data, timeout=30)
        print(f"AI Proxy response status: {response.status_code}")
        
        if response.status_code != 200:
            response_text = response.text[:200]  # Limit output for logs
            print(f"Error response: {response_text}")
            return f"Error: API returned status code {response.status_code}: {response_text}"
        
        # Extract cost information from headers for logging
        cost = response.headers.get('cost', 'unknown')
        monthly_cost = response.headers.get('monthlyCost', 'unknown')
        monthly_requests = response.headers.get('monthlyRequests', 'unknown')
        print(f"Request cost: ${cost}, Monthly cost: ${monthly_cost}, Monthly requests: {monthly_requests}")
        
        response_json = response.json()
        
        if "choices" not in response_json or len(response_json["choices"]) == 0:
            print(f"Unexpected response format: {response_json}")
            return f"Error: Unexpected response format"
            
        answer = response_json["choices"][0]["message"]["content"].strip()
        return answer
        
    except requests.exceptions.Timeout:
        print("Request to AI Proxy timed out")
        return "Error: Request to AI Proxy timed out"
    except requests.exceptions.ConnectionError as e:
        print(f"Connection error when contacting AI Proxy: {str(e)}")
        return f"Error: Connection error: {str(e)}"
    except Exception as e:
        print(f"ERROR in generate_answer: {str(e)}")
        print(traceback.format_exc())
        return f"Error: {str(e)}"

@app.get("/health")
async def health_check():
    """Simple endpoint to verify the API is running"""
    return {
        "status": "ok", 
        "token_configured": bool(AIPROXY_TOKEN),
        "token_prefix": AIPROXY_TOKEN[:5] + "..." if AIPROXY_TOKEN else None,
        "aiproxy_url": AIPROXY_BASE_URL
    }

@app.get("/test-aiproxy")
async def test_aiproxy():
    """Test connection to AI Proxy without sending a full request"""
    try:
        # Test the models endpoint which should be lightweight
        test_url = f"{AIPROXY_BASE_URL}/v1/models"
        headers = {
            "Authorization": f"Bearer {AIPROXY_TOKEN}"
        }
        
        response = requests.get(test_url, headers=headers, timeout=5)
        
        return {
            "status": "success" if response.status_code == 200 else "error",
            "status_code": response.status_code,
            "url_tested": test_url,
            "response": response.json() if response.status_code == 200 else response.text[:100]
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "url_tested": f"{AIPROXY_BASE_URL}/v1/models"
        }

@app.get("/")
async def root():
    """Root endpoint that shows API documentation"""
    return {
        "service": "Question Answering API",
        "endpoints": {
            "/api/": "POST - Process a question with optional file upload",
            "/health": "GET - Check API health and configuration",
            "/test-aiproxy": "GET - Test connection to AI Proxy"
        },
        "version": "1.0"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
