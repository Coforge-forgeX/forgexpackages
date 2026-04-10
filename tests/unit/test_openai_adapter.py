
from common_adapters.ai.openai import OpenAIAdapter

class FakeClient:
    def generate(self, prompt: str, model: str) -> str:
        return f"{model}::{prompt}"

def test_generate():
    a = OpenAIAdapter(FakeClient(), 'm')
    assert a.generate('hi') == 'm::hi'
