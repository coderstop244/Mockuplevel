# Mockuplevel

Mockuplevel is an AI-assisted learning and study application designed to help users work with learning materials and interact with their content. The intended workflow includes uploading documents or videos, processing the content, asking questions, and using learning tools such as quizzes and progress tracking.

> **Project note:** Check the current repository and `.env.example` before running the project. Exact scripts, environment-variable names, and feature availability can change as development continues.
> 

## Contents

- Features
- Technology
- Prerequisites
- Getting Started
- Environment Configuration
- Run the Application
- Using Mockuplevel
- How Media Processing Works
- Troubleshooting
- Development
- Security Notes

## Features

Depending on the current implementation and configuration, the project is intended to support:

- **Learning-material uploads:** Work with supported documents such as PDF and PowerPoint (`.pptx`).
- **Video-based learning:** Upload a video for background processing and use the extracted content to ask questions, if video processing is enabled.
- **AI tutor/chat:** Ask questions about processed learning material.
- **Quizzes and assessments:** Practice with questions based on learning content, where implemented.
- **Progress and analytics:** Review learning activity and progress, where implemented.
- **Asynchronous processing:** Use a task worker and Redis so longer media-processing jobs do not have to run inside the web request.
- **Content retrieval:** Store and retrieve processed content for relevant question answering, depending on the configured database/vector-search integration.

## Technology

The repository has been developed around components including:

- **Python / FastAPI** for backend API services
- **Celery** for background jobs
- **Redis** as the task broker
- **Supabase** for configured database and related services
- **FFmpeg** for media handling
- **Whisper** for speech transcription, if enabled
- **A vector database / embedding retrieval layer** for searching processed content, according to the repository configuration
- **React and JavaScript** for the frontend, if the frontend is included in the checked-out branch

Use the dependency files and configuration in the repository as the source of truth for the exact stack.

## Prerequisites

Install the tools required by the parts of the project you intend to run:

- Git
- Python version supported by the project’s dependency files
- Node.js and npm, if running the React frontend
- Redis
- FFmpeg, for video/audio processing
- Access credentials for the configured Supabase project
- Any API keys required by the AI model, embedding, or transcription services used in your configuration

Verify installations:

```powershell
git --version
python --version
node --version
npm --version
ffmpeg -version
redis-server --version
```

Some Windows Redis installations do not provide `redis-server` as a command. In that case, run Redis using your existing Redis installation or a supported local/container setup.

## Getting Started

### 1. Clone the repository

Open PowerShell or a terminal:

```powershell
git clone https://github.com/coderstop244/Mockuplevel.git
cd Mockuplevel
```

The repository may contain nested folders. Locate the backend and frontend directories before running commands:

```powershell
Get-ChildItem
```

If the project files are inside a nested `Mockuplevel` directory, change into that directory before continuing.

### 2. Create and activate a Python virtual environment

From the directory containing the backend’s Python dependency file:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, you can activate the environment from Command Prompt instead:

```bash
.venv\Scripts\activate.bat
```

### 3. Install backend dependencies

Use the dependency file that actually exists in the backend directory.

For `requirements.txt`:

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If the project uses `pyproject.toml`, Poetry, or another dependency manager instead, follow that file’s instructions rather than installing from a nonexistent `requirements.txt`.

### 4. Configure environment variables

Find the example configuration file, if provided:

```powershell
Get-ChildItem -Force -Name .env*
```

Copy the example file and edit the copy:

```powershell
Copy-Item .env.example .env
```

Only run that command if `.env.example` exists. If the example file has another name, copy that file instead. Fill in the variable names required by the code and documentation. See Environment Configuration.

### 5. Start Redis

Start Redis using your installed service or local setup. In a separate terminal, verify that it responds:

```powershell
redis-cli ping
```

Expected response:

```
PONG
```

If the command is unavailable or Redis is running in a container, use the matching command for your installation. The Redis URL configured for the application must point to the same Redis instance.

## Environment Configuration

The application may need configuration for:

- Supabase URL and key(s)
- Redis connection URL
- AI provider/model API key(s)
- Embedding or vector database connection details
- Upload/storage settings
- Backend host, port, and frontend API base URL

**Do not guess environment-variable names.** Check `.env.example`, settings modules, and the code that reads environment variables. Use the exact names expected by the checked-out version.

Example only — replace the placeholders and variable names with those documented in your repository:

```
# Example placeholders only; use the exact names required by the project.
SUPABASE_URL=your_supabase_project_url
SUPABASE_KEY=your_supabase_key
REDIS_URL=redis://localhost:6379/0
AI_API_KEY=your_ai_provider_key
```

The variables above are illustrative and may not match the actual names used by this project. Never commit a real `.env` file, API keys, database passwords, or service-role keys to Git.

## Run the Application

The repository’s actual entry points and scripts take precedence over these examples.

### Backend API

From the backend directory, activate the virtual environment and run the FastAPI application using the entry point defined in the project. A common pattern is:

```powershell
uvicorn src.main:app --reload
```

Use this command only if the application entry point is `src/main.py` and it exposes `app`. If the repository uses a different module, find the correct entry point in its source code or existing run instructions.

When the server starts, open the API documentation at:

```
http://127.0.0.1:8000/docs
```

This URL is the default for the example command; use the host and port printed by your server if they differ.

### Celery worker

Open a **separate terminal** in the backend directory, activate the same virtual environment, and run the worker using the Celery app configured in the repository. If the app is defined at `src/tasks/celery_worker.py` as `celery_app`, the command may be:

```powershell
celery -A src.tasks.celery_worker.celery_app worker --loglevel=info --pool=solo
```

On Windows, `--pool=solo` is often useful for local development. If your Celery app is located elsewhere, update the `-A` path to match the actual module and object name.

Keep Redis, the API server, and the worker running while testing background processing. Starting the API alone does not guarantee that queued video-processing jobs will be executed.

### Frontend

If a frontend directory contains `package.json`, open another terminal and enter that directory. For example, if it is named `frontend`:

```powershell
cd frontend
npm install
npm run dev
```

Check `package.json` for the available scripts. Vite projects commonly start on a URL such as `http://localhost:5173`, but use the URL printed in your terminal.

If the frontend is not in a folder named `frontend`, use the directory that actually contains its `package.json`.

## Using Mockuplevel

Once all required services are running:

1. **Open the frontend** using the local URL printed by its development server.
2. **Sign in or create an account** if authentication is configured.
3. **Upload supported material.** Choose a PDF, PowerPoint file, or video only if that file type is supported by the current UI and backend.
4. **Wait for processing to finish.** A video may need time for audio extraction, transcription, text chunking, embeddings, and storage. Large files can take longer.
5. **Check the processing status.** If the UI shows a job status, wait for a completed/success state before asking content-based questions.
6. **Ask questions in the AI chat/tutor.** Use questions about the material you uploaded. Answers depend on successful processing and retrieval.
7. **Use quizzes and progress views** if those screens and backend endpoints are implemented in your current branch.

If an upload appears successful but the content is unavailable to the AI tutor, check the API response, worker logs, Redis connection, database records, and processing status.

## How Media Processing Works

A typical video-processing flow for this architecture is:

1. The user uploads a video through the frontend.
2. The backend validates the request and stores or references the uploaded file.
3. The backend queues a processing task.
4. Redis delivers the task to a Celery worker.
5. The worker uses FFmpeg or related tools to extract audio or prepare media.
6. A transcription service such as Whisper converts speech to text, if enabled.
7. The text is split into chunks and may be embedded and stored for retrieval.
8. The application uses the processed content to support question answering.

The exact steps depend on the code and enabled services. A queued job is not proof that processing has started; check worker logs and task state.

## Troubleshooting

### Video upload succeeds, but processing never finishes

- Confirm Redis is running and that the API and worker use the same Redis URL.
- Confirm the Celery worker started successfully and is listening to the expected queue.
- Inspect worker logs for import errors, missing environment variables, or task exceptions.
- Check whether the task remains `PENDING`, becomes `STARTED`, or ends in `FAILURE`, using the status mechanism implemented by the project.
- Confirm the worker can access the uploaded file and any storage URL.
- Run `ffmpeg -version` and check that FFmpeg is available to the worker process.
- Confirm transcription/model credentials are valid and required model files are available.
- Check disk space, file size limits, and network access to configured services.

### `ModuleNotFoundError` or import errors

- Activate the project’s virtual environment.
- Install dependencies from the correct dependency file.
- Run commands from the directory expected by the project.
- Verify the Celery `A` path and the FastAPI import path match the real files.

### Supabase connection or authentication errors

- Verify the project URL and key against the Supabase project settings.
- Check the environment variable names used by the code.
- Confirm the required tables, policies, buckets, and migrations exist.
- Never expose service-role credentials in frontend code.

### Frontend cannot reach the backend

- Confirm the backend is running and note its actual host and port.
- Check the frontend’s API base URL and environment configuration.
- Inspect browser developer tools for failed requests and CORS errors.
- Confirm the backend permits requests from the frontend’s development origin.

### AI answers do not reflect the uploaded material

- Confirm processing completed successfully.
- Check whether extracted text/transcription was stored.
- Verify embeddings and vector-search configuration, if used.
- Confirm the question-answer endpoint retrieves content belonging to the correct user and document.
- Review backend and worker logs for errors.

## Development

Before making changes:

```powershell
git pull
git status
```

Create a branch for your work:

```powershell
git switch -c feature/your-feature-name
```

After testing your changes:

```powershell
git add .
git commit -m "Describe your change"
git push -u origin feature/your-feature-name
```

Open a pull request on GitHub and describe the changes, setup requirements, and tests performed. Do not commit `.env`, credentials, large generated media files, or local virtual environments.

## Security Notes

- Keep secrets in environment variables or an appropriate secrets manager.
- Ensure `.env` and credential files are excluded by `.gitignore`.
- Do not expose Supabase service-role keys or private AI API keys to the browser.
- Validate file type and size on the backend, not only in the frontend.
- Apply authentication and authorization checks to uploads, document retrieval, chat, and processing-status endpoints.
- Treat uploaded documents and media as untrusted input.
- Configure production CORS, storage access, and logging before deployment.

## Support

For bugs or setup questions, open an issue in the repository:

https://github.com/coderstop244/Mockuplevel/issues

When reporting a problem, include the operating system, Python and Node versions, the command you ran, the relevant error message, and sanitized backend/worker logs. Remove API keys, tokens, passwords, and personal data before sharing logs.

---

**Maintainer:** Contributors to coderstop244/Mockuplevel

**License:** Check the repository for a `LICENSE` file before redistributing or reusing the project.
