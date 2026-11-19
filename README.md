
# Task Management API

A Django REST Framework application that converts natural-language task descriptions into structured tasks. It supports task management, subtasks, automatic task breakdown, idempotent requests, validation, filtering, searching, ordering, and pagination.

## Features

- Create, retrieve, update, and delete tasks.
- Create tasks from natural-language descriptions.
- Rule-based task parsing with an LLM-powered parser.
- Create and list subtasks.
- Automatically break down tasks into smaller subtasks.
- Idempotency support for safe retries.
- Consistent API error responses.
- Filter, search, order, and paginate tasks.
- PostgreSQL database integration.

## Technology Stack

- Python 3.11
- Django 5.2
- Django REST Framework
- PostgreSQL 16
- django-filter
- Ollama with Qwen3 4B
- Postman for API testing

## Project Structure

```text

task-management-api/
│
├── config/
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
│
├── tasks/
│   ├── migrations/
│   ├── models.py
│   ├── serializers.py
│   ├── views.py
│   ├── urls.py
│   ├── parser.py
│   ├── parser_interface.py
│   ├── llm_parser.py
│   ├── breakdown.py
│   ├── exceptions.py
│   └── tests.py
│
├── .env.example
├── .gitignore
├── manage.py
├── requirements.txt
├── openapi.yaml
└── README.md

```

## Installation and Setup

### 1. Clone the repository

```bash
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd task-management-api
```

### 2. Create a virtual environment

```bash
python -m venv .venv
```

Activate it on Windows:

```cmd
.venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure PostgreSQL

Create a PostgreSQL database named:

```text
task_management_db
```

Configure your `.env` file in the project root:

```env
DJANGO_SECRET_KEY=replace-with-your-secret-key
DB_NAME=task_management_db
DB_USER=postgres
DB_PASSWORD=your_postgres_password
DB_HOST=localhost
DB_PORT=5433
```

Never commit `.env` or database credentials to GitHub.

### 5. Run migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

### 6. Start the development server

```bash
python manage.py runserver
```

API base URL:

```text
http://127.0.0.1:8000/api/
```

## API Endpoints

### Task Management

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/tasks/` | List tasks |
| POST | `/api/tasks/` | Create a task |
| GET | `/api/tasks/{id}/` | Retrieve a task |
| PUT | `/api/tasks/{id}/` | Update a task |
| PATCH | `/api/tasks/{id}/` | Partially update a task |
| DELETE | `/api/tasks/{id}/` | Delete a task |

### Natural Language Task Creation

**POST** `/api/tasks/from-text/`

Request:

```json
{
  "text": "Remind me to pay rent on the 1st of every month"
}
```

This endpoint converts natural-language input into structured task data.

### Subtasks

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/tasks/{id}/subtasks/` | List subtasks |
| POST | `/api/tasks/{id}/subtasks/` | Create a subtask |
| POST | `/api/tasks/{id}/breakdown/` | Generate subtasks automatically |

### Filtering, Searching and Ordering

Examples:

```text
/api/tasks/?priority=high
/api/tasks/?completed=false
/api/tasks/?search=rent
/api/tasks/?ordering=-created_at
/api/tasks/?page=1&page_size=10
/api/tasks/?due_date=2026-11-20
/api/tasks/?parent=1
```

## Idempotency

The API supports an optional `Idempotency-Key` header on:

- `POST /api/tasks/`
- `POST /api/tasks/from-text/`
- `POST /api/tasks/{id}/breakdown/`

Behaviour:

- Same key and same request body: returns the original response.
- Same key and different request body: returns HTTP 422.
- Successful responses are stored for retries.
- Failed requests are not retained as successful responses.

## Standard Error Response

All validation and not-found errors use a consistent structure.

Example:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Validation failed",
    "details": [
      {
        "field": "title",
        "issue": "must not be empty"
      }
    ]
  }
}
```

## Running Tests

Run the complete test suite:

```bash
python manage.py test
```

The project currently includes 30 automated tests

## Natural Language Parser

The project supports natural-language task creation through a parser function:

```python
parse_task_text(text, today)
```

The rule-based parser is implemented in `tasks/parser.py`.

It supports:
- Today and tomorrow.
- Relative dates such as "in 3 days".
- Monthly recurrence.
- Weekly recurrence.
- Daily recurrence.
- Monthly recurrence days such as "1st of every month".
- Validation of conflicting date and recurrence instructions.
- Month-end date handling.

The parser returns structured task data containing:
- title
- description
- due_date
- priority
- recurrence

The LLM-powered implementation is separately maintained in `tasks/llm_parser.py` and currently uses a locally running Ollama Qwen3 4B model.


### LLM Integration

The project also supports an LLM-powered parser using Ollama and the Qwen3 4B model.

**Configuration:**

- Ollama URL: `http://localhost:11434/api/chat`
- Model: `qwen3:4b`
- Timeout: 120 seconds
- Response format: JSON

**Setup:**

1. Install Ollama on your machine.
2. Download the model:

```bash
ollama pull qwen3:4b
```

3. Start the Ollama service.
4. Start the Django development server.

The LLM parser extracts task title, description, due date, priority, and recurrence information.

The returned data is validated using `TaskSerializer` before saving it to PostgreSQL.



## API Documentation

The handwritten OpenAPI specification is available in:

```text
openapi.yaml
```

## Testing Improvements

The AI-generated test checklist was reviewed and expanded to cover cases such as invalid dates, invalid Boolean values, invalid parent IDs, malformed LLM output, parser failures, repeated idempotency keys, and transaction rollback.

Additional tests were added to verify idempotent task creation and breakdown retries.
