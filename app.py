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
    # Create a temporary directory for file processing
    with tempfile.TemporaryDirectory() as temp_dir:
        file_paths = []
        file_contents = {}
        
        # Process uploaded file if present
        if file and file.filename:
            file_path = os.path.join(temp_dir, file.filename)
            
            # Save the uploaded file
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            file_paths.append(file_path)
            
            # Handle ZIP files
            if file.filename.endswith('.zip'):
                extract_dir = os.path.join(temp_dir, "extracted")
                os.makedirs(extract_dir, exist_ok=True)
                
                with zipfile.ZipFile(file_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_dir)
                
                # Process extracted files
                for root, _, files in os.walk(extract_dir):
                    for extracted_file in files:
                        extracted_path = os.path.join(root, extracted_file)
                        file_paths.append(extracted_path)
                        
                        # Read CSV files
                        if extracted_file.endswith('.csv'):
                            try:
                                df = pd.read_csv(extracted_path)
                                # Limit the data to prevent timeout
                                if len(df) > 100:
                                    file_contents[extracted_file] = f"CSV with {len(df)} rows and {len(df.columns)} columns.\n"
                                    file_contents[extracted_file] += f"Column names: {', '.join(df.columns.tolist())}\n"
                                    file_contents[extracted_file] += f"First 5 rows:\n{df.head(5).to_string()}\n"
                                    if "answer" in df.columns:
                                        file_contents[extracted_file] += f"\nValues in 'answer' column: {df['answer'].tolist()}"
                                else:
                                    file_contents[extracted_file] = df.to_string()
                            except Exception as e:
                                # If pandas fails, try with csv module
                                try:
                                    with open(extracted_path, 'r') as f:
                                        reader = csv.reader(f)
                                        rows = list(reader)
                                        if len(rows) > 0:
                                            headers = rows[0]
                                            answer_col_index = -1
                                            if "answer" in headers:
                                                answer_col_index = headers.index("answer")
                                            
                                            file_contents[extracted_file] = f"CSV with {len(rows)} rows.\n"
                                            file_contents[extracted_file] += f"Headers: {', '.join(headers)}\n"
                                            
                                            if answer_col_index >= 0:
                                                answer_values = [row[answer_col_index] for row in rows[1:] if len(row) > answer_col_index]
                                                file_contents[extracted_file] += f"Values in 'answer' column: {answer_values}"
                                except Exception as e:
                                    file_contents[extracted_file] = f"Error reading file: {str(e)}"
        
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
