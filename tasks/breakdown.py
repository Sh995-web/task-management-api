from abc import ABC, abstractmethod


class TaskBreakdownProvider(ABC):
    """
    Common interface for all task breakdown providers.
    """

    @abstractmethod
    def generate(self, task):
        """
        Generate subtasks for the given task.
        """
        pass

class RuleBasedProvider(TaskBreakdownProvider):

    def generate(self, task):

        task_text = f"{task.title} {task.description}".lower()

        if any(word in task_text for word in ["trip", "travel", "holiday"]):

            return [
                {
                    "title": "Decide destination and travel dates",
                    "description": "Choose the destination and finalize travel dates"
                },
                {
                    "title": "Book transportation",
                    "description": "Research and book suitable transportation"
                },
                {
                    "title": "Reserve accommodation",
                    "description": "Find and book suitable accommodation"
                },
                {
                    "title": "Prepare travel itinerary",
                    "description": "Plan destinations and activities for the holiday"
                },
                {
                    "title": "Estimate travel budget",
                    "description": "Calculate transportation, accommodation and activity expenses"
                }
            ]

        return [
            {
                "title": f"Understand: {task.title}",
                "description": f"Review the requirements: {task.description}"
            },
            {
                "title": f"Plan: {task.title}",
                "description": f"Create an execution plan for: {task.description}"
            },
            {
                "title": f"Execute: {task.title}",
                "description": f"Complete the activities described in: {task.description}"
            },
            {
                "title": f"Review: {task.title}",
                "description": "Review and verify the completed work"
            }
        ]