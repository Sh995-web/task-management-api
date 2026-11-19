import json
import urllib.request
import urllib.error

from datetime import date


OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "qwen3:4b"


def parse_with_llm(task_text, today):

    prompt = f"""
You are a task extraction API. Convert the user's instruction into structured task data.

Today's date: {today}
User instruction: {task_text}

Return exactly these five fields:
- title: short task name
- description: original user instruction
- due_date: YYYY-MM-DD string, or null
- priority: low, medium, or high
- recurrence: null or an object

Rules:
1. Always include all five fields.
2. Never replace title with description.
3. Use medium priority unless urgency is explicitly stated.
4. For monthly recurrence, use:
   {{"frequency": "monthly", "day": 1}}
5. For weekly recurrence, use:
   {{"frequency": "weekly"}}
6. For daily recurrence, use:
   {{"frequency": "daily"}}
7. Calculate the next due date for recurring tasks.
8. Return valid JSON only. No explanations.

Example:
{{
    "title": "Pay rent",
    "description": "Pay rent on the 1st of every month",
    "due_date": "2026-12-01",
    "priority": "medium",
    "recurrence": {{"frequency": "monthly", "day": 1}}
}}
"""

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "stream": False,
        "think": False,
        "format": "json",
        "options": {
            "temperature": 0,
            "num_predict": 150
        }
    }

    request_data = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        OLLAMA_URL,
        data=request_data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            response_data = json.loads(
                response.read().decode("utf-8")
            )

        content = response_data["message"]["content"]
        parsed_data = json.loads(content)

        # 1. Validate JSON structure.
        required_fields = {
            "title",
            "description",
            "due_date",
            "priority",
            "recurrence"
        }

        if not isinstance(parsed_data, dict):
            raise ValueError("LLM response must be a JSON object.")

        if set(parsed_data.keys()) != required_fields:
            raise ValueError(
                "LLM response has missing or unexpected fields."
            )

        # 2. Validate title.
        if (
            not isinstance(parsed_data["title"], str)
            or not parsed_data["title"].strip()
        ):
            raise ValueError("LLM returned an invalid title.")

        # 3. Validate description.
        if (
            not isinstance(parsed_data["description"], str)
            or not parsed_data["description"].strip()
        ):
            raise ValueError("LLM returned an invalid description.")

        # 4. Validate priority.
        if parsed_data["priority"] not in ["low", "medium", "high"]:
            raise ValueError("LLM returned an invalid priority.")

        # 5. Validate due date.
        if parsed_data["due_date"] is not None:
            if not isinstance(parsed_data["due_date"], str):
                raise ValueError("Due date must be a string or null.")

            parsed_data["due_date"] = date.fromisoformat(
                parsed_data["due_date"]
            )

        # 6. Validate recurrence.
        recurrence = parsed_data["recurrence"]

        if recurrence is not None:
            if not isinstance(recurrence, dict):
                raise ValueError("LLM returned invalid recurrence data.")

            frequency = recurrence.get("frequency")

            if frequency not in ["daily", "weekly", "monthly"]:
                raise ValueError("Invalid recurrence frequency.")

            if frequency == "monthly":
                day = recurrence.get("day")

                if (
                    not isinstance(day, int)
                    or isinstance(day, bool)
                    or not 1 <= day <= 31
                ):
                    raise ValueError("Invalid monthly recurrence day.")

        return parsed_data

    except Exception as exc:
        raise RuntimeError(
            f"LLM parsing or validation failed: {exc}"
        ) from exc
