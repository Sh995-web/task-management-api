import re
import calendar
from datetime import date, timedelta


def parse_task_text(text, today):
    """
    Convert natural-language task text into structured task data.
    """

    text = text.strip().lower()

    if not text:
        raise ValueError("Task text cannot be empty")

    title = text

    # Remove common reminder phrases
    prefixes = [
        "remind me to ",
        "remind me ",
        "please ",
        "i need to ",
        "i have to "
    ]

    for prefix in prefixes:
        if title.startswith(prefix):
            title = title[len(prefix):]
            break

    # Remove date and recurrence phrases from the title
    date_patterns = [
        r"\s+tomorrow\b",
        r"\s+today\b",
        r"\s+in \d+ days?\b",
        r"\s+on the \d{1,2}(?:st|nd|rd|th)? of every month\b",
        r"\s+every month\b",
        r"\s+monthly\b",
        r"\s+every day\b",
        r"\s+daily\b",
        r"\s+every week\b",
        r"\s+weekly\b"
    ]

    for pattern in date_patterns:
        title = re.sub(pattern, "", title)

    title = title.strip().capitalize()

    # Initialize task properties
    due_date = None
    recurrence = None
    recurrence_day = None

    # Detect today and tomorrow
    date_options = []

    if "today" in text:
        date_options.append(today)

    if "tomorrow" in text:
        date_options.append(today + timedelta(days=1))

    # Reject conflicting date instructions
    if len(date_options) > 1:
        raise ValueError(
            "Please specify only one due date."
        )

    if date_options:
        due_date = date_options[0]

    # Detect all relative day expressions
    days_matches = re.findall(r"\bin (\d+) days?\b", text)

    if len(days_matches) > 1:
        raise ValueError(
            "Please specify only one due date."
        )

    if days_matches:
        if date_options:
            raise ValueError(
                "Please specify only one due date."
            )

        number_of_days = int(days_matches[0])
        due_date = today + timedelta(days=number_of_days)

    # Detect recurrence frequency
    recurrence_options = []

    if "every month" in text or "monthly" in text:
        recurrence_options.append("monthly")

    if "every week" in text or "weekly" in text:
        recurrence_options.append("weekly")

    if "every day" in text or "daily" in text:
        recurrence_options.append("daily")

    # Reject conflicting recurrence instructions
    if len(recurrence_options) > 1:
        raise ValueError(
            "Please specify only one recurrence frequency."
        )

    recurrence = recurrence_options[0] if recurrence_options else None

    # Extract recurrence day
    match = re.search(
        r"on the (\d{1,2})(?:st|nd|rd|th)? of every month",
        text
    )

    if match:
        recurrence_day = int(match.group(1))

    # Validate recurrence day
    if recurrence_day is not None:
        if recurrence_day < 1 or recurrence_day > 31:
            raise ValueError(
                "Recurrence day must be between 1 and 31"
            )

    # Calculate next monthly due date
    if recurrence == "monthly" and recurrence_day is not None:

        if recurrence_day >= today.day:
            year = today.year
            month = today.month
        else:
            if today.month == 12:
                year = today.year + 1
                month = 1
            else:
                year = today.year
                month = today.month + 1

        last_day = calendar.monthrange(year, month)[1]
        actual_day = min(recurrence_day, last_day)

        due_date = date(year, month, actual_day)

    # Build recurrence dictionary
    recurrence_data = None

    if recurrence == "monthly":
        recurrence_data = {
            "frequency": "monthly",
            "day": recurrence_day
        }

    elif recurrence == "weekly":
        recurrence_data = {
            "frequency": "weekly"
        }

    elif recurrence == "daily":
        recurrence_data = {
            "frequency": "daily"
        }

    # Return structured task data
    return {
        "title": title,
        "description": text,
        "due_date": due_date,
        "priority": "medium",
        "recurrence": recurrence_data
    }
