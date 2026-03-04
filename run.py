#!/usr/bin/env python3
"""atom-0 — dead-simple chat CLI with tool use"""

import json
import os
import subprocess
import urllib.request

LLM_URL = os.environ.get("LLM_URL", "https://api.novaqore.ai/v1/chat/completions")
MODEL = os.environ.get("LLM_MODEL", "qwen3.5")
SYSTEM = "You are Atom, a helpful assistant. You have access to tools. When you need to run a command, use the bash tool."

TOOLS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools")

# ANSI colors
BLUE = "\033[34m"
WHITE = "\033[97m"
GRAY = "\033[90m"
RESET = "\033[0m"


def load_tools():
    tools = []
    if not os.path.isdir(TOOLS_DIR):
        return tools
    for f in sorted(os.listdir(TOOLS_DIR)):
        if f.endswith(".json"):
            with open(os.path.join(TOOLS_DIR, f)) as fh:
                tools.append(json.load(fh))
    return tools


def run_tool(name, args):
    if name == "bash":
        cmd = args.get("command", "")
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=30
            )
            output = result.stdout
            if result.stderr:
                output += result.stderr
            return output.strip() or "(no output)"
        except subprocess.TimeoutExpired:
            return "(command timed out after 30s)"
    return f"(unknown tool: {name})"


def stream_chat(messages, tools):
    payload = {
        "model": MODEL,
        "messages": messages,
        "stream": True,
    }
    if tools:
        payload["tools"] = tools

    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        LLM_URL, data=body, headers={"Content-Type": "application/json"}
    )

    with urllib.request.urlopen(req) as resp:
        buf = b""
        content_parts = []
        tool_calls = {}  # index -> {id, name, arguments}

        for chunk in iter(lambda: resp.read(1), b""):
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                line = line.strip()
                if not line or line == b"data: [DONE]":
                    continue
                if not line.startswith(b"data: "):
                    continue
                try:
                    obj = json.loads(line[6:])
                    delta = obj["choices"][0].get("delta", {})

                    # content tokens
                    token = delta.get("content")
                    if token:
                        print(token, end="", flush=True)
                        content_parts.append(token)

                    # tool call chunks
                    for tc in delta.get("tool_calls", []):
                        idx = tc["index"]
                        if idx not in tool_calls:
                            tool_calls[idx] = {
                                "id": tc.get("id", f"call_{idx}"),
                                "name": tc.get("function", {}).get("name", ""),
                                "arguments": "",
                            }
                        if tc.get("id"):
                            tool_calls[idx]["id"] = tc["id"]
                        if tc.get("function", {}).get("name"):
                            tool_calls[idx]["name"] = tc["function"]["name"]
                        tool_calls[idx]["arguments"] += tc.get("function", {}).get("arguments", "")

                except (json.JSONDecodeError, KeyError, IndexError):
                    pass

        if content_parts:
            print(RESET)

        content = "".join(content_parts) or None
        tc_list = None
        if tool_calls:
            tc_list = [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {"name": tc["name"], "arguments": tc["arguments"]},
                }
                for tc in sorted(tool_calls.values(), key=lambda x: x["id"])
            ]

        return content, tc_list


def main():
    os.system("clear")
    tools = load_tools()
    messages = [{"role": "system", "content": SYSTEM}]
    print("atom-0  (Ctrl+C to exit)\n")

    while True:
        try:
            user_input = input(f"{WHITE}You: {GRAY}").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"{RESET}\nBye.")
            break

        if not user_input:
            continue

        messages.append({"role": "user", "content": user_input})

        # loop: LLM may call tools multiple times before giving a final answer
        while True:
            print(f"{BLUE}Atom: {WHITE}", end="", flush=True)
            try:
                content, tool_calls = stream_chat(messages, tools)
            except Exception as e:
                print(f"{RESET}\n[error] {e}")
                messages.pop()
                break

            # build assistant message
            assistant_msg = {"role": "assistant"}
            if content:
                assistant_msg["content"] = content
            if tool_calls:
                assistant_msg["tool_calls"] = tool_calls
            messages.append(assistant_msg)

            if not tool_calls:
                break

            # execute each tool call
            for tc in tool_calls:
                name = tc["function"]["name"]
                try:
                    args = json.loads(tc["function"]["arguments"])
                except json.JSONDecodeError:
                    args = {}

                print(f"{GRAY}  [{name}] {args.get('command', args)}")
                result = run_tool(name, args)
                print(f"  → {result[:200]}{'...' if len(result) > 200 else ''}{RESET}")

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result,
                })


if __name__ == "__main__":
    main()
