#!/usr/bin/env python3
"""atom-0 — dead-simple chat CLI for local Qwen 3.5 9B"""

import json
import os
import sys
import urllib.request

LLM_URL = os.environ.get("LLM_URL", "http://localhost:19400/v1/chat/completions")
MODEL = os.environ.get("LLM_MODEL", "qwen3.5")
SYSTEM = "You are Atom, a helpful assistant."


def stream_chat(messages):
    body = json.dumps({
        "model": MODEL,
        "messages": messages,
        "stream": True,
    }).encode()

    req = urllib.request.Request(
        LLM_URL,
        data=body,
        headers={"Content-Type": "application/json"},
    )

    with urllib.request.urlopen(req) as resp:
        buf = b""
        full = []
        for chunk in iter(lambda: resp.read(1), b""):
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                line = line.strip()
                if not line or line == b"data: [DONE]":
                    continue
                if line.startswith(b"data: "):
                    try:
                        obj = json.loads(line[6:])
                        delta = obj["choices"][0].get("delta", {})
                        token = delta.get("content")
                        if token:
                            print(token, end="", flush=True)
                            full.append(token)
                    except (json.JSONDecodeError, KeyError, IndexError):
                        pass
        print()
        return "".join(full)


def main():
    messages = [{"role": "system", "content": SYSTEM}]
    print("atom-0  (Ctrl+C to exit)\n")

    while True:
        try:
            user_input = input("You > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            break

        if not user_input:
            continue

        messages.append({"role": "user", "content": user_input})
        print("Atom > ", end="", flush=True)

        try:
            reply = stream_chat(messages)
            messages.append({"role": "assistant", "content": reply})
        except Exception as e:
            print(f"\n[error] {e}")
            messages.pop()  # remove failed user msg


if __name__ == "__main__":
    main()
