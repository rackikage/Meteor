"""AI adapter — HTTP chat client. Replaceable; talks to any Ollama-compatible endpoint.

Per doctrine: adapters isolate change. Swap this file for a real Meteor runtime
client when one exists. The interface is `stream_chat(messages, url, model, on_chunk)`.
"""
import json
import urllib.request


def stream_chat(messages: list, url: str, model: str, on_chunk) -> None:
    body = json.dumps({
        "model": model,
        "messages": messages,
        "stream": True,
    }).encode()
    req = urllib.request.Request(
        url.rstrip("/") + "/api/chat",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        for line in resp:
            line = line.decode().strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            chunk = d.get("message", {}).get("content", "")
            if chunk:
                on_chunk(chunk)
