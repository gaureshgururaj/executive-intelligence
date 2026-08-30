from typing import Protocol


class LlmClient(Protocol):
    """Provider-agnostic LLM interface.

    Domain code depends on this protocol, not a vendor SDK.
    """

    def complete(self, prompt: str) -> str: ...
