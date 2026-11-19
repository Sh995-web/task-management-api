import hashlib
import json
from rest_framework import viewsets, filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.pagination import PageNumberPagination
from .serializers import TaskSerializer, TaskTextSerializer
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from .breakdown import RuleBasedProvider
from .exceptions import error_response
from django.utils import timezone
from .parser_interface import get_task_parser
from django.db import IntegrityError, transaction
from .models import Task, IdempotencyRecord



def check_idempotency(request):
    """
    Check whether this request has already been processed.
    """

    key = request.headers.get("Idempotency-Key")

    # Idempotency is optional.
    if not key:
        return None, None

    # Create a consistent hash of the request body.
    request_body = json.dumps(
        request.data,
        sort_keys=True,
        separators=(",", ":"),
        default=str
    )

    request_hash = hashlib.sha256(
        request_body.encode("utf-8")
    ).hexdigest()

    # Atomically create or retrieve the idempotency record.
    with transaction.atomic():
        record, created = IdempotencyRecord.objects.get_or_create(
            key=key,
            defaults={"request_hash": request_hash}
        )

        record = IdempotencyRecord.objects.select_for_update().get(
            pk=record.pk
        )

    # Same key cannot be reused with different request data.
    if record.request_hash != request_hash:
        return None, error_response(
            "IDEMPOTENCY_KEY_CONFLICT",
            "Idempotency key was already used with different request data.",
            [
                {
                    "field": "Idempotency-Key",
                    "issue": "Use a new key for a different request."
                }
            ],
            status.HTTP_422_UNPROCESSABLE_ENTITY
        )

    # Return the original response if the request succeeded previously.
    if record.response_body is not None:
        return None, Response(
            record.response_body,
            status=record.status_code
        )

    # A previous request with this key is still being processed.
    if not created:
        return None, error_response(
            "REQUEST_IN_PROGRESS",
            "A request with this idempotency key is already in progress.",
            [
                {
                    "field": "Idempotency-Key",
                    "issue": "Retry this request shortly."
                }
            ],
            status.HTTP_409_CONFLICT
        )

    return record, None


def complete_idempotency(record, response):
    """Store the successful response for future retries."""

    if record is not None:
        record.response_body = json.loads(
            json.dumps(response.data, default=str)
        )
        record.status_code = response.status_code

        record.save(
            update_fields=["response_body", "status_code"]
        )

    return response


def release_idempotency(record):
    """Remove a reservation when request processing fails."""

    if record is not None:
        record.delete()



class TaskPagination(PageNumberPagination):
    page_size = 2
    page_size_query_param = "page_size"
    max_page_size = 100


class TaskViewSet(viewsets.ModelViewSet):

    queryset = Task.objects.all().order_by("-created_at")
    serializer_class = TaskSerializer
    pagination_class = TaskPagination

    # Filtering, searching and ordering
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]

    # Exact field filtering
    filterset_fields = [
        "priority",
        "completed",
        "due_date",
        "parent",
    ]

    # Text search
    search_fields = [
        "title",
        "description",
    ]

    # Allowed sorting fields
    ordering_fields = [
        "created_at",
        "due_date",
        "priority",
        "title",
    ]

    # Default sorting: newest first
    ordering = ["-created_at"]

    def create(self, request, *args, **kwargs):

        # Check idempotency key
        record, cached_response = check_idempotency(request)

        if cached_response is not None:
            return cached_response

        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            task = serializer.save()

            response = Response(
                self.get_serializer(task).data,
                status=status.HTTP_201_CREATED
            )

            return complete_idempotency(record, response)

        except Exception:
            release_idempotency(record)
            raise


    @action(detail=True, methods=["get", "post"], url_path="subtasks")
    def subtasks(self, request, pk=None):

    # Get the parent task using the ID from the URL
        parent_task = self.get_object()

    # GET: Retrieve all subtasks belonging to this parent
        if request.method == "GET":
            subtasks = parent_task.subtasks.all()

            serializer = self.get_serializer(subtasks, many=True)

            return Response(serializer.data, status=status.HTTP_200_OK)

    # POST: Create a new subtask
        if request.method == "POST":
            data = request.data.copy()

        # Automatically assign the parent task ID
            data["parent"] = parent_task.id

            serializer = self.get_serializer(data=data)

            serializer.is_valid(raise_exception=True)

            serializer.save()

            return Response(
            serializer.data,
            status=status.HTTP_201_CREATED
        )

    
    @action(detail=True, methods=["post"], url_path="breakdown")
    def breakdown(self, request, pk=None):

        # Step 1: Retrieve the parent task
        parent_task = self.get_object()

        # Step 2: Check idempotency
        record, cached_response = check_idempotency(request)

        if cached_response is not None:
            return cached_response

        try:
            # Step 3: Prevent breaking down a subtask
            if parent_task.parent_id is not None:
                release_idempotency(record)
                return error_response(
                    "VALIDATION_ERROR",
                    "Validation failed",
                    [{
                        "field": "parent",
                        "issue": "A subtask cannot be broken down."
                    }],
                    status.HTTP_400_BAD_REQUEST
                )

            # Step 4: Generate subtasks
            provider = RuleBasedProvider()
            generated_subtasks = provider.generate(parent_task)

            if not generated_subtasks:
                release_idempotency(record)
                return error_response(
                    "VALIDATION_ERROR",
                    "Validation failed",
                    [{
                        "field": "breakdown",
                        "issue": "No subtasks could be generated."
                    }],
                    status.HTTP_400_BAD_REQUEST
                )

            # Step 5: Validate and save all subtasks atomically
            created_subtasks = []

            with transaction.atomic():

                for subtask_data in generated_subtasks:
                    subtask_data["parent"] = parent_task.id

                    serializer = TaskSerializer(data=subtask_data)
                    serializer.is_valid(raise_exception=True)

                    created_subtasks.append(serializer.save())

                # Step 6: Prepare response
                response_serializer = TaskSerializer(
                    created_subtasks,
                    many=True
                )

                response = Response(
                    response_serializer.data,
                    status=status.HTTP_201_CREATED
                )

                # Step 7: Store response for retries
                return complete_idempotency(record, response)

        except Exception:
            release_idempotency(record)
            raise

    
    @action(detail=False, methods=["post"], url_path="from-text")
    def from_text(self, request):

        # 1. Validate incoming request.
        input_serializer = TaskTextSerializer(data=request.data)

        if not input_serializer.is_valid():
            return error_response(
                "VALIDATION_ERROR",
                "Validation failed",
                [
                    {"field": field, "issue": str(issue)}
                    for field, errors in input_serializer.errors.items()
                    for issue in errors
                ],
                status.HTTP_400_BAD_REQUEST
            )

        task_text = input_serializer.validated_data["text"]

        # 2. Check idempotency key.
        record, cached_response = check_idempotency(request)

        if cached_response is not None:
            return cached_response

        try:
            # 3. Generate structured task data using the LLM.
            parser = get_task_parser()

            parsed_data = parser.parse(
            task_text,
            timezone.localdate()
            )

            # 4. Validate LLM output using TaskSerializer.
            task_serializer = TaskSerializer(data=parsed_data)

            if not task_serializer.is_valid():
                release_idempotency(record)

                return error_response(
                    "PARSER_ERROR",
                    "Parser returned invalid task data",
                    [
                        {"field": field, "issue": str(issue)}
                        for field, errors in task_serializer.errors.items()
                        for issue in errors
                    ],
                    status.HTTP_502_BAD_GATEWAY
                )

            # 5. Save the task.
            task = task_serializer.save()

            response = Response(
                TaskSerializer(task).data,
                status=status.HTTP_201_CREATED
            )

            # 6. Save response for future retries.
            return complete_idempotency(record, response)

        except Exception:
            release_idempotency(record)

            return error_response(
                "PARSER_ERROR",
                "Task parsing failed",
                [
                    {
                        "field": "text",
                        "issue": "Unable to process task text."
                    }
                ],
                status.HTTP_502_BAD_GATEWAY
            )
