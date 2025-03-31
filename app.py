import os
import shutil
import tempfile
import zipfile
import json
import requests
from pathlib import Path
import pandas as pd
import csv
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# AI Proxy configuration
AIPROXY_URL = "https://api.aiproxy.pro/v1/run"
AIPROXY_TOKEN = os.environ.get("AIPROXY_TOKEN")

@app.post("/api/")
async def process_question(
    question: str = Form(...),
    file: UploadFile = File(None)
):
    temp_dir = "/tmp"  # Use Vercel-compatible temp storage
    file_paths = []
    file_contents = {}

    if file and file.filename:
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

    answer = await generate_answer(question, file_contents)
    return {"answer": answer}


async def generate_answer(question: str, file_contents: dict = None):
    # Prepare a concise prompt with file contents if available
    prompt = f"Answer this question directly and concisely: {question}\n"
    
    if file_contents:
        prompt += "File contents:\n"
        for filename, content in file_contents.items():
            prompt += f"--- {filename} ---\n{content}\n\n"
    
    prompt += "Return ONLY the answer value, nothing else. No explanations."
    
    # Make the API call to AI Proxy (GPT-4o-Mini)
    headers = {
        "Authorization": f"Bearer {AIPROXY_TOKEN}",
        "Content-Type": "application/json"
    }
    
    data = {
        "prompt": prompt,
        "model": "gpt-4o-mini"
    }
    
    try:
        response = requests.post(AIPROXY_URL, headers=headers, json=data)
        response.raise_for_status()
        answer = response.json()["text"].strip()
        
        # Clean up the answer to ensure it's just the value
        answer = answer.strip('"').strip("'")
        return answer
    except Exception as e:
        return f"Error: {str(e)}"

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
