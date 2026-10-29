"""Optional provider adapter. Import and credentials are checked only when explicitly used."""
import os

def generate_with_groq(prompt: str) -> str:
    key=os.getenv('GROQ_API_KEY')
    if not key:
        raise RuntimeError('Groq is unavailable: set GROQ_API_KEY to enable this optional adapter.')
    try:
        from groq import Groq
    except ImportError as exc:
        raise RuntimeError('Groq adapter dependency is unavailable. Install the optional groq package.') from exc
    client=Groq(api_key=key)
    response=client.chat.completions.create(model=os.getenv('GROQ_MODEL','llama-3.3-70b-versatile'),messages=[{'role':'user','content':prompt}],temperature=0)
    return response.choices[0].message.content or ''
