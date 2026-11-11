"""Chat with the model that solves riddles, for anything else you want to ask it.

It's the same llama-server, which has one slot and a 2048-token context. So a
riddle must never wait behind a chat reply: cancelling hangs up mid-reply, which
also stops the server generating, and the history is trimmed to fit.
"""
import http.client
import json

from riddle import FACT_MIN_COVERAGE, PORT

SYSTEM = ("You are the assistant built into MASSAB, a helper for the Roblox game Steal a Brainrot. "
          "Answer clearly and keep it short unless asked for detail. Use Markdown for lists and code. "
          "If facts are given, trust them over your memory, and say so when you aren't sure.")
MAX_REPLY_TOKENS = 512
# About 4 characters a token, leaving room for the system prompt, facts and the reply.
HISTORY_CHARS = 3200
FACTS_LIMIT = 4
ERRORS = (OSError, http.client.HTTPException, ValueError, KeyError, IndexError)


def trim_history(history, limit=HISTORY_CHARS):
    """The newest messages that fit in limit characters, starting with one of the user's.
    The last message is always kept, cut down if it's too long by itself."""
    kept, used = [], 0
    for message in reversed(history):
        used += len(message["content"])
        if kept and used > limit:
            break
        kept.append(message)
    kept.reverse()
    while len(kept) > 1 and kept[0]["role"] != "user":
        kept.pop(0)
    if kept and len(kept[-1]["content"]) > limit:
        kept[-1] = {**kept[-1], "content": kept[-1]["content"][:limit]}
    return kept


def pick_facts(facts, question):
    """Fact sheet lines that cover the question, or none if they only share a word with it."""
    lines, coverage = facts.top(facts.unglue(question), FACTS_LIMIT)
    return lines if coverage >= FACT_MIN_COVERAGE else []


def build_messages(history, facts=(), date_line="", live=""):
    """date_line is today's date (today.describe), and live is what was looked
    up online (lookup.live_section). Both take room from the history."""
    system = SYSTEM
    if date_line:
        system += f"\n\n{date_line}"
    if facts:
        system += "\n\nFacts about the game that may help:\n" + "\n".join(f"- {fact}" for fact in facts)
    if live:
        system += f"\n\n{live}"
    return [{"role": "system", "content": system}, *trim_history(history, max(800, HISTORY_CHARS - len(live)))]


def stream_reply(messages, on_text, cancelled, port=PORT, timeout=60):
    """Ask for a reply and stream it. on_text gets the reply so far after each piece.

    Returns the whole reply, or None once cancelled (a threading.Event) is set.
    """
    body = json.dumps({
        "messages": messages, "temperature": 0.6, "top_p": 0.9, "max_tokens": MAX_REPLY_TOKENS, "stream": True,
        "chat_template_kwargs": {"enable_thinking": False},
    })
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
    reply = ""
    try:
        conn.request("POST", "/v1/chat/completions", body, {"Content-Type": "application/json"})
        response = conn.getresponse()
        if response.status != 200:
            raise ValueError(f"the AI said {response.status}")
        for line in response:
            if cancelled.is_set():
                return None
            if line.startswith(b"data: ") and not line.startswith(b"data: [DONE]"):
                choices = json.loads(line[6:])["choices"]
                piece = (choices[0]["delta"].get("content") or "") if choices else ""
                if piece:
                    reply += piece
                    on_text(reply)
    finally:
        conn.close()
    return None if cancelled.is_set() else reply
