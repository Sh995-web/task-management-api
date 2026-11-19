from rest_framework.response import Response
from rest_framework.views import exception_handler
from rest_framework.exceptions import ValidationError, NotFound
from django.http import Http404

def error_response(code, message, details, status_code):
    return Response(
        {
            "error": {
                "code": code,
                "message": message,
                "details": details,
            }
        },
        status=status_code,
    )

def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is None:
        return None

    if isinstance(exc, ValidationError):
        code = "VALIDATION_ERROR"
        message = "Validation failed"
    elif isinstance(exc, (NotFound, Http404)):
        code = "NOT_FOUND"
        message = "Resource not found"
    else:
        code = "API_ERROR"
        message = "An API error occurred"

    details = []

    if isinstance(response.data, dict):
        for field, errors in response.data.items():
            for error in errors if isinstance(errors, list) else [errors]:
                details.append({
                    "field": field,
                    "issue": str(error)
                })
    else:
        details.append({
            "field": "non_field_errors",
            "issue": str(response.data)
        })

    response.data = {
        "error": {
            "code": code,
            "message": message,
            "details": details
        }
    }

    return response