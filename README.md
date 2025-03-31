# IIT Madras Data Science Assignment Solver API

This is an API that automatically answers questions from the IIT Madras Online Degree in Data Science graded assignments. It uses GPT-4o-Mini via AI Proxy to generate answers based on the questions and any attached files.

## API Endpoint

The API is deployed at: `https://your-app.vercel.app/api/`

## Usage

Send a POST request to the API endpoint with the question and any required files as multipart/form-data.

Example using curl:

```bash
curl -X POST "https://your-app.vercel.app/api/" \
  -H "Content-Type: multipart/form-data" \
  -F "question=Download and unzip file abcd.zip which has a single extract.csv file inside. What is the value in the \"answer\" column of the CSV file?" \
  -F "file=@abcd.zip"
```

The API will return a JSON response with the answer:

```json
{
  "answer": "1234567890"
}
```

## Features

- Processes questions from all 5 graded assignments
- Handles file attachments (including ZIP files)
- Extracts and processes CSV files automatically
- Returns answers in the required JSON format

## Setup for Local Development

1. Clone this repository
2. Install dependencies: `pip install -r requirements.txt`
3. Set your AI Proxy token as an environment variable: `export AIPROXY_TOKEN=your_token_here`
4. Run the application: `uvicorn app:app --reload`

## Deployment

This application can be deployed to Vercel or any other platform that supports Python applications. Make sure to set the `AIPROXY_TOKEN` environment variable in your deployment platform.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
