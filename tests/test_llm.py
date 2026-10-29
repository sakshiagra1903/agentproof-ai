import pytest
from app.services.llm import generate_with_groq

def test_groq_missing_key_is_clear(monkeypatch):
 monkeypatch.delenv('GROQ_API_KEY',raising=False)
 with pytest.raises(RuntimeError,match='GROQ_API_KEY'): generate_with_groq('hello')


def test_groq_mocked_response(monkeypatch):
    import sys, types
    class FakeCompletions:
        def create(self, **kwargs):
            return types.SimpleNamespace(choices=[types.SimpleNamespace(message=types.SimpleNamespace(content='mock answer'))])
    class FakeClient:
        def __init__(self, api_key): self.chat=types.SimpleNamespace(completions=FakeCompletions())
    monkeypatch.setenv('GROQ_API_KEY','test-only-not-a-real-key')
    monkeypatch.setitem(sys.modules,'groq',types.SimpleNamespace(Groq=FakeClient))
    assert generate_with_groq('hello')=='mock answer'
