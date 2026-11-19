from rest_framework.test import APITestCase
from rest_framework import status
from unittest.mock import patch
from tasks.breakdown import RuleBasedProvider
from tasks.models import IdempotencyRecord
import hashlib
import json
from datetime import date
from tasks.parser import parse_task_text
from tasks.models import Task


class TaskAPITests(APITestCase):

    def test_create_task_successfully(self):
        data = {
            "title": "Test task",
            "description": "Testing task creation",
            "completed": False,
            "priority": "medium",
        }

        response = self.client.post("/api/tasks/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["title"], "Test task")

    def test_list_tasks(self):
        data = {
            "title": "Test task",
            "description": "Testing task listing",
            "completed": False,
            "priority": "medium",
        }

        self.client.post("/api/tasks/", data, format="json")

        response = self.client.get("/api/tasks/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)


    
    def test_retrieve_existing_task(self):
        create_response = self.client.post(
            "/api/tasks/",
            {
                "title": "Retrieve task",
                "description": "Test retrieving a task",
                "completed": False,
                "priority": "medium",
            },
            format="json",
        )

        task_id = create_response.data["id"]

        response = self.client.get(f"/api/tasks/{task_id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "Retrieve task")

    def test_update_task_with_put(self):
        create_response = self.client.post(
            "/api/tasks/",
            {
                "title": "Old title",
                "description": "Old description",
                "completed": False,
                "priority": "low",
            },
            format="json",
        )

        task_id = create_response.data["id"]

        updated_data = {
            "title": "Updated title",
            "description": "Updated description",
            "completed": True,
            "priority": "high",
        }

        response = self.client.put(
            f"/api/tasks/{task_id}/",
            updated_data,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "Updated title")
        self.assertEqual(response.data["completed"], True)
        self.assertEqual(response.data["priority"], "high")

    def test_partial_update_task_with_patch(self):
        create_response = self.client.post(
            "/api/tasks/",
            {
                "title": "Original title",
                "description": "Original description",
                "completed": False,
                "priority": "medium",
            },
            format="json",
        )

        task_id = create_response.data["id"]

        response = self.client.patch(
            f"/api/tasks/{task_id}/",
            {"title": "Partially updated title"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "Partially updated title")
        self.assertEqual(response.data["description"], "Original description")

    def test_delete_task(self):
        create_response = self.client.post(
            "/api/tasks/",
            {
                "title": "Task to delete",
                "description": "This task will be deleted",
                "completed": False,
                "priority": "medium",
            },
            format="json",
        )

        task_id = create_response.data["id"]

        response = self.client.delete(f"/api/tasks/{task_id}/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        retrieve_response = self.client.get(f"/api/tasks/{task_id}/")

        self.assertEqual(
            retrieve_response.status_code,
            status.HTTP_404_NOT_FOUND,
        )


    def test_create_task_with_empty_title_fails(self):
        data = {
            "title": "",
            "description": "Testing invalid task",
            "completed": False,
            "priority": "medium",
        }

        response = self.client.post("/api/tasks/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["code"], "VALIDATION_ERROR")

    def test_retrieve_nonexistent_task_returns_404(self):
        response = self.client.get("/api/tasks/99999/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["error"]["code"], "NOT_FOUND")

    def test_invalid_priority_fails(self):
        data = {
            "title": "Test task",
            "description": "Testing invalid priority",
            "completed": False,
            "priority": "urgent",
        }

        response = self.client.post("/api/tasks/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["code"], "VALIDATION_ERROR")

    def test_create_subtask_successfully(self):
        parent_data = {
            "title": "Plan a trip",
            "description": "Plan the complete trip",
            "completed": False,
            "priority": "high",
        }

        parent_response = self.client.post(
            "/api/tasks/", parent_data, format="json"
        )

        parent_id = parent_response.data["id"]

        subtask_data = {
            "title": "Book hotel",
            "description": "Book hotel for the trip",
            "completed": False,
            "priority": "medium",
        }

        response = self.client.post(
            f"/api/tasks/{parent_id}/subtasks/",
            subtask_data,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["parent"], parent_id)

    def test_nested_subtasks_are_rejected(self):
        parent_data = {
            "title": "Plan a trip",
            "description": "Plan the complete trip",
            "completed": False,
            "priority": "high",
        }

        parent_response = self.client.post(
            "/api/tasks/", parent_data, format="json"
        )
        parent_id = parent_response.data["id"]

        subtask_data = {
            "title": "Book hotel",
            "description": "Book hotel for the trip",
            "completed": False,
            "priority": "medium",
        }

        subtask_response = self.client.post(
            f"/api/tasks/{parent_id}/subtasks/",
            subtask_data,
            format="json",
        )
        subtask_id = subtask_response.data["id"]

        nested_data = {
            "title": "Compare hotel prices",
            "description": "Compare hotel prices",
            "completed": False,
            "priority": "low",
        }

        response = self.client.post(
            f"/api/tasks/{subtask_id}/subtasks/",
            nested_data,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["code"], "VALIDATION_ERROR")

    def test_parent_with_subtasks_cannot_become_subtask(self):
        first_parent = {
            "title": "Plan a trip",
            "description": "Plan the trip",
            "completed": False,
            "priority": "high",
        }

        first_response = self.client.post(
            "/api/tasks/", first_parent, format="json"
        )
        first_parent_id = first_response.data["id"]

        second_parent = {
            "title": "Plan another trip",
            "description": "Plan another trip",
            "completed": False,
            "priority": "medium",
        }

        second_response = self.client.post(
            "/api/tasks/", second_parent, format="json"
        )
        second_parent_id = second_response.data["id"]

        child_data = {
            "title": "Book hotel",
            "description": "Book hotel",
            "completed": False,
            "priority": "medium",
        }

        self.client.post(
            f"/api/tasks/{first_parent_id}/subtasks/",
            child_data,
            format="json",
        )

        response = self.client.patch(
            f"/api/tasks/{first_parent_id}/",
            {"parent": second_parent_id},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["code"], "VALIDATION_ERROR")



    def test_filter_tasks_by_priority(self):
        tasks_data = [
            {
                "title": "High priority task",
                "description": "Urgent task",
                "completed": False,
                "priority": "high",
            },
            {
                "title": "Low priority task",
                "description": "Non urgent task",
                "completed": False,
                "priority": "low",
            },
        ]

        for task_data in tasks_data:
            self.client.post("/api/tasks/", task_data, format="json")

        response = self.client.get("/api/tasks/?priority=high")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        tasks = response.data["results"]

        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["priority"], "high")
        self.assertEqual(tasks[0]["title"], "High priority task")

    def test_search_tasks_by_title(self):
        data = [
            {
                "title": "Prepare Python interview",
                "description": "Study Python concepts",
                "completed": False,
                "priority": "high",
            },
            {
                "title": "Buy groceries",
                "description": "Buy milk and bread",
                "completed": False,
                "priority": "low",
            },
        ]

        for task_data in data:
            self.client.post("/api/tasks/", task_data, format="json")

        response = self.client.get("/api/tasks/?search=Python")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        results = response.data["results"]

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Prepare Python interview")      


    def test_order_tasks_by_title(self):
        tasks_data = [
            {
                "title": "Zebra task",
                "description": "Last alphabetically",
                "completed": False,
                "priority": "medium",
            },
            {
                "title": "Apple task",
                "description": "First alphabetically",
                "completed": False,
                "priority": "medium",
            },
        ]

        for task_data in tasks_data:
            self.client.post("/api/tasks/", task_data, format="json")

        response = self.client.get("/api/tasks/?ordering=title")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        results = response.data["results"]

        self.assertEqual(results[0]["title"], "Apple task")
        self.assertEqual(results[1]["title"], "Zebra task")


    def test_task_pagination(self):
        for i in range(3):
            data = {
                "title": f"Task {i}",
                "description": f"Description {i}",
                "completed": False,
                "priority": "medium",
            }
            self.client.post("/api/tasks/", data, format="json")

        response = self.client.get("/api/tasks/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 3)
        self.assertEqual(len(response.data["results"]), 2)

        second_page = self.client.get("/api/tasks/?page=2")

        self.assertEqual(second_page.status_code, status.HTTP_200_OK)
        self.assertEqual(len(second_page.data["results"]), 1)


    def test_task_breakdown_creates_subtasks(self):
        parent_data = {
            "title": "Plan a trip",
            "description": "Plan a complete trip",
            "completed": False,
            "priority": "high",
        }

        parent_response = self.client.post(
            "/api/tasks/", parent_data, format="json"
        )
        parent_id = parent_response.data["id"]

        response = self.client.post(
            f"/api/tasks/{parent_id}/breakdown/",
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        subtask_response = self.client.get(
            f"/api/tasks/{parent_id}/subtasks/"
        )

        self.assertEqual(subtask_response.status_code, status.HTTP_200_OK)
        self.assertGreater(len(subtask_response.data), 0)

    
    def test_breakdown_idempotent_retry(self):
        parent = Task.objects.create(
            title="Plan a trip",
            description="Plan a complete trip",
            priority="high",
        )

        url = f"/api/tasks/{parent.id}/breakdown/"

        first_response = self.client.post(
            url,
            {},
            format="json",
            HTTP_IDEMPOTENCY_KEY="breakdown-test-001",
        )

        second_response = self.client.post(
            url,
            {},
            format="json",
            HTTP_IDEMPOTENCY_KEY="breakdown-test-001",
        )

        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second_response.status_code, status.HTTP_201_CREATED)

        self.assertEqual(first_response.data, second_response.data)

        self.assertEqual(parent.subtasks.count(), len(first_response.data))


    @patch("tasks.parser_interface.LLMTaskParser.parse")
    def test_idempotent_retry_returns_same_task(self, mock_parser):
            mock_parser.return_value = {
            "title": "Pay rent",
            "description": "Pay rent tomorrow",
            "due_date": None,
            "priority": "medium",
            "recurrence": None,
        }

            data = {"text": "Pay rent tomorrow"}
            headers = {"HTTP_IDEMPOTENCY_KEY": "test-key-001"}

            first_response = self.client.post(
                "/api/tasks/from-text/",
                data,
                format="json",
                **headers,
        )

            second_response = self.client.post(
                "/api/tasks/from-text/",
                data,
                 format="json",
                **headers,
        )

            self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
            self.assertEqual(second_response.status_code, status.HTTP_201_CREATED)
            self.assertEqual(first_response.data["id"], second_response.data["id"])
            self.assertEqual(mock_parser.call_count, 1)

    @patch("tasks.parser_interface.LLMTaskParser.parse")
    def test_idempotency_key_rejects_different_request(self, mock_parser):
        mock_parser.return_value = {
            "title": "Pay rent",
            "description": "Pay rent tomorrow",
            "due_date": None,
            "priority": "medium",
            "recurrence": None,
        }

        headers = {"HTTP_IDEMPOTENCY_KEY": "test-key-002"}

        first_response = self.client.post(
            "/api/tasks/from-text/",
            {"text": "Pay rent tomorrow"},
            format="json",
            **headers,
        )

        second_response = self.client.post(
            "/api/tasks/from-text/",
            {"text": "Buy groceries tomorrow"},
            format="json",
            **headers,
        )

        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second_response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertEqual(
            second_response.data["error"]["code"],
            "IDEMPOTENCY_KEY_CONFLICT",
        )
        self.assertEqual(mock_parser.call_count, 1)

    @patch("tasks.views.RuleBasedProvider")
    def test_breakdown_rolls_back_invalid_subtasks(self, mock_provider_class):
        parent_data = {
            "title": "Plan a trip",
            "description": "Plan a complete trip",
            "completed": False,
            "priority": "high",
        }

        parent_response = self.client.post(
            "/api/tasks/", parent_data, format="json"
        )
        parent_id = parent_response.data["id"]

        mock_provider = mock_provider_class.return_value
        mock_provider.generate.return_value = [
            {
                "title": "Valid subtask",
                "description": "This subtask is valid",
                "priority": "medium",
            },
            {
                "title": "",
                "description": "This subtask is invalid",
                "priority": "medium",
            },
        ]

        response = self.client.post(
            f"/api/tasks/{parent_id}/breakdown/",
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        subtask_response = self.client.get(
            f"/api/tasks/{parent_id}/subtasks/"
        )

        self.assertEqual(subtask_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(subtask_response.data), 0)


    @patch("tasks.parser_interface.LLMTaskParser.parse")
    def test_empty_task_text_is_rejected(self, mock_parser):
        response = self.client.post(
            "/api/tasks/from-text/",
            {"text": ""},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertEqual(
            response.data["error"]["code"],
            "VALIDATION_ERROR",
        )

        mock_parser.assert_not_called()

    
    def test_incomplete_idempotency_record_returns_409(self):
        request_hash = hashlib.sha256(
            json.dumps(
                {"text": "Pay rent tomorrow"},
                sort_keys=True,
                separators=(",", ":"),
                default=str
            ).encode("utf-8")
        ).hexdigest()

        IdempotencyRecord.objects.create(
            key="test-in-progress-key",
            request_hash=request_hash,
            response_body=None,
            status_code=None,
        )

        response = self.client.post(
            "/api/tasks/from-text/",
            {"text": "Pay rent tomorrow"},
            format="json",
            HTTP_IDEMPOTENCY_KEY="test-in-progress-key",
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(
            response.data["error"]["code"],
            "REQUEST_IN_PROGRESS",
        )

    
    @patch("tasks.parser_interface.LLMTaskParser.parse")
    def test_llm_failure_returns_structured_error(self, mock_parser):
        mock_parser.side_effect = Exception("Ollama server unavailable")

        response = self.client.post(
            "/api/tasks/from-text/",
            {"text": "Pay rent tomorrow"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_502_BAD_GATEWAY,
        )

        self.assertEqual(
            response.data["error"]["code"],
            "PARSER_ERROR",
        )

        self.assertEqual(
            response.data["error"]["message"],
            "Task parsing failed",
        )

    
    @patch("tasks.parser_interface.LLMTaskParser.parse")
    def test_invalid_llm_output_returns_structured_error(self, mock_parser):
        mock_parser.return_value = {
            "title": "",
            "description": "",
            "completed": False,
            "due_date": None,
            "priority": "invalid",
            "recurrence": None,
        }

        response = self.client.post(
            "/api/tasks/from-text/",
            {"text": "Pay rent tomorrow"},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_502_BAD_GATEWAY,
        )

        self.assertEqual(
            response.data["error"]["code"],
            "PARSER_ERROR",
        )

        self.assertEqual(
            response.data["error"]["message"],
            "Parser returned invalid task data",
        )

    
    def test_invalid_due_date_is_rejected(self):
        response = self.client.post(
            "/api/tasks/",
            {
                "title": "Pay rent",
                "description": "Pay monthly rent",
                "due_date": "not-a-valid-date",
                "priority": "high",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertEqual(
            response.data["error"]["code"],
            "VALIDATION_ERROR",
        )

    def test_invalid_completed_value_is_rejected(self):
        response = self.client.post(
            "/api/tasks/",
            {
                "title": "Pay rent",
                "description": "Pay monthly rent",
                "completed": "not-a-boolean",
                "priority": "high",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertEqual(
            response.data["error"]["code"],
            "VALIDATION_ERROR",
        )

    
    def test_invalid_parent_id_is_rejected(self):
        response = self.client.post(
            "/api/tasks/",
            {
                "title": "Prepare report",
                "description": "Complete the project report",
                "priority": "medium",
                "parent": 999999,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

        self.assertEqual(
            response.data["error"]["code"],
            "VALIDATION_ERROR",
        )

    def test_monthly_recurrence_is_parsed_correctly(self):
        result = parse_task_text(
            "Remind me to pay rent on the 1st of every month",
            date(2026, 11, 18),
        )

        self.assertIsNotNone(result["recurrence"])
        self.assertEqual(result["recurrence"]["frequency"], "monthly")
        self.assertEqual(result["recurrence"]["day"], 1)



    def test_task_creation_idempotent_retry(self):
        payload = {
            "title": "Complete project",
            "description": "Finish the Django API",
            "priority": "high",
        }

        first_response = self.client.post(
            "/api/tasks/",
            payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY="task-create-001",
        )

        second_response = self.client.post(
            "/api/tasks/",
            payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY="task-create-001",
        )

        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second_response.status_code, status.HTTP_201_CREATED)

        self.assertEqual(
            first_response.data["id"],
            second_response.data["id"],
        )

        self.assertEqual(Task.objects.count(), 1)




