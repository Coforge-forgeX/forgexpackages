
from tenacity import retry, wait_exponential, stop_after_attempt
from common_adapters.ai.base import LLMAdapter

class OpenAIAdapter(LLMAdapter):
    def __init__(self, client, model: str):
        self._client = client
        self._model = model

    @retry(wait=wait_exponential(multiplier=1, min=1, max=8), stop=stop_after_attempt(3), reraise=True)
    def generate(self, prompt: str) -> str:
        return self._client.generate(prompt=prompt, model=self._model)
