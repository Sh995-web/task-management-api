from rest_framework import serializers
from .models import Task


class TaskSerializer(serializers.ModelSerializer):

    class Meta:
        model = Task
        fields = [
            "id",
            "title",
            "description",
            "completed",
            "due_date",
            "priority",
            "parent",
            "recurrence",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_title(self, value):

        if not value or not value.strip():
            raise serializers.ValidationError("must not be empty")

        return value.strip()

    def validate_description(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("must not be empty")

        return value.strip()

    def validate_priority(self, value):
        allowed_priorities = ["low", "medium", "high"]

        if value not in allowed_priorities:
            raise serializers.ValidationError(
                "must be one of: low, medium, high"
            )

        return value

    def validate(self, attrs):
        parent = attrs.get("parent")

    # A subtask cannot be attached to another subtask.
        if parent and parent.parent_id is not None:
            raise serializers.ValidationError({
            "parent": "A subtask cannot have its own subtasks."
        })

    # A task that already has subtasks cannot itself become a subtask.
        if self.instance and self.instance.subtasks.exists() and parent is not None:
         raise serializers.ValidationError({
            "parent": "A task with existing subtasks cannot become a subtask."
        })

        return attrs


class TaskTextSerializer(serializers.Serializer):
    text = serializers.CharField(
        required=True,
        allow_blank=False,
        trim_whitespace=True
    )

    def validate_text(self, value):
        if not value.strip():
            raise serializers.ValidationError(
                "Task text cannot be empty."
            )
        return value.strip()
