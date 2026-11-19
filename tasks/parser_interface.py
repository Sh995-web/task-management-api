
from abc import ABC, abstractmethod

from django.conf import settings
from django.utils.module_loading import import_string

from .parser import parse_task_text
from .llm_parser import parse_with_llm


class TaskParser(ABC):

    @abstractmethod
    def parse(self, text, today):
        pass


class RuleBasedTaskParser(TaskParser):

    def parse(self, text, today):
        return parse_task_text(text, today)


class LLMTaskParser(TaskParser):

    def parse(self, text, today):
        return parse_with_llm(text, today)


def get_task_parser():
    parser_class = import_string(settings.TASK_PARSER)
    return parser_class()
