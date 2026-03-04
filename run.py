#!/usr/bin/env python3
"""atom-0 — dead-simple chat CLI with tool use"""

import itertools
import json
import os
import subprocess
import sys
import threading
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from system_prompt import SYSTEM

LLM_URL = os.environ.get("LLM_URL", "https://api.novaqore.ai/v1/chat/completions")
MODEL = os.environ.get("LLM_MODEL", "qwen3.5")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TOOLS_DIR = os.path.join(BASE_DIR, "tools")
CUSTOM_TOOLS_DIR = os.path.join(os.path.expanduser("~"), ".atom-0-tools")
HISTORY_FILE = os.path.join(BASE_DIR, "chat_history.json")

# ANSI
BLUE = "\033[34m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
WHITE = "\033[97m"
GRAY = "\033[90m"
RESET = "\033[0m"
BOLD = "\033[1m"
BOLD_OFF = "\033[22m"
CODE_ON = "\033[36;48;5;236m"
CODE_OFF = "\033[0m\033[97m"
CLEAR_LINE = "\r\033[K"

SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]


# --- spinner ---

class Spinner:
    def __init__(self, label="working...", color=YELLOW):
        self._label = label
        self._color = color
        self._stop = threading.Event()
        self._thread = None
        self._frames = itertools.cycle(SPINNER_FRAMES)
        self._active = False

    def start(self):
        if self._active:
            return
        self._stop.clear()
        self._active = True
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()

    def _spin(self):
        while not self._stop.is_set():
            sys.stdout.write(f"{CLEAR_LINE}{self._color}{next(self._frames)} {self._label}{RESET}")
            sys.stdout.flush()
            time.sleep(0.08)

    def stop(self):
        if not self._active:
            return
        self._stop.set()
        self._thread.join()
        self._thread = None
        self._active = False
        sys.stdout.write(CLEAR_LINE)
        sys.stdout.flush()


# --- markdown ---

def format_token(token, state):
    out = ""
    for ch in token:
        if not state["code"] and ch == "*":
            state["stars"] += 1
            continue
        if state["stars"]:
            if state["stars"] >= 2:
                state["bold"] = not state["bold"]
                out += BOLD if state["bold"] else BOLD_OFF
                state["stars"] -= 2
            out += "*" * state["stars"]
            state["stars"] = 0
        if ch == "`":
            state["code"] = not state["code"]
            out += CODE_ON if state["code"] else CODE_OFF
        else:
            out += ch
    return out


# --- tools ---

def load_tools():
    tools = []
    for d in (TOOLS_DIR, CUSTOM_TOOLS_DIR):
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            if f.endswith(".json"):
                with open(os.path.join(d, f)) as fh:
                    tools.append(json.load(fh))
    return tools


def run_tool(name, args):
    if name == "tool_maker":
        tool_name = args.get("name", "")
        definition = args.get("definition", "")
        os.makedirs(CUSTOM_TOOLS_DIR, exist_ok=True)
        path = os.path.join(CUSTOM_TOOLS_DIR, f"{tool_name}.json")
        try:
            parsed = json.loads(definition)
            with open(path, "w") as fh:
                json.dump(parsed, fh, indent=2)
            return f"Tool '{tool_name}' saved to {path}. RELOAD_TOOLS"
        except json.JSONDecodeError as e:
            return f"Invalid JSON definition: {e}"

    cmd = args.get("command", "")
    if not cmd:
        return f"(no command provided for tool: {name})"
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        out = r.stdout + r.stderr
        return out.strip() or "(no output)"
    except subprocess.TimeoutExpired:
        return "(timed out)"


# --- streaming ---

def parse_sse(resp):
    """Yield (delta, usage) tuples from an SSE response."""
    buf = b""
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
                usage = obj.get("usage")
                choices = obj.get("choices", [])
                delta = choices[0].get("delta", {}) if choices else {}
                yield delta, usage
            except (json.JSONDecodeError, KeyError, IndexError):
                pass


def stream_chat(messages, tools, spinner_label="loading...", spinner_color=BLUE):
    payload = {"model": MODEL, "messages": messages, "stream": True, "stream_options": {"include_usage": True}}
    if tools:
        payload["tools"] = tools

    req = urllib.request.Request(
        LLM_URL,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )

    responding = Spinner(spinner_label, spinner_color)
    working = Spinner("working...", YELLOW)
    responding.start()

    md = {"code": False, "bold": False, "stars": 0}
    content_parts = []
    content_ended = False
    tool_calls = {}
    usage = None

    with urllib.request.urlopen(req) as resp:
        for delta, chunk_usage in parse_sse(resp):
            if chunk_usage:
                usage = chunk_usage

            # tool call chunks — swap to yellow working spinner
            if delta.get("tool_calls"):
                if not tool_calls:
                    if content_parts and not content_ended:
                        sys.stdout.write(f"{RESET}\n")
                        sys.stdout.flush()
                        content_ended = True
                    responding.stop()
                    working.start()
                for tc in delta["tool_calls"]:
                    idx = tc["index"]
                    if idx not in tool_calls:
                        tool_calls[idx] = {"id": tc.get("id", f"call_{idx}"), "name": tc.get("function", {}).get("name", ""), "arguments": ""}
                    if tc.get("id"):
                        tool_calls[idx]["id"] = tc["id"]
                    if tc.get("function", {}).get("name"):
                        tool_calls[idx]["name"] = tc["function"]["name"]
                    tool_calls[idx]["arguments"] += tc.get("function", {}).get("arguments", "")

            # content tokens — stop spinner, print immediately
            token = delta.get("content")
            if token:
                if not content_parts:
                    responding.stop()
                    sys.stdout.write(f"{BLUE}Atom: {WHITE}")
                    sys.stdout.flush()
                sys.stdout.write(format_token(token, md))
                sys.stdout.flush()
                content_parts.append(token)

    responding.stop()
    working.stop()

    if content_parts and not content_ended:
        sys.stdout.write(f"{RESET}\n")
        sys.stdout.flush()

    # show token usage
    if usage:
        p = usage.get('prompt_tokens', 0)
        c = usage.get('completion_tokens', 0)
        t = usage.get('total_tokens', 0)
        sys.stdout.write(f"{GRAY}{p}:{c} - {t}/262144{RESET}\n")
        sys.stdout.flush()

    content = "".join(content_parts) or None
    tc_list = None
    if tool_calls:
        tc_list = [
            {"id": tc["id"], "type": "function", "function": {"name": tc["name"], "arguments": tc["arguments"]}}
            for tc in sorted(tool_calls.values(), key=lambda x: x["id"])
        ]
    return content, tc_list


# --- main ---

def load_history():
    if os.path.isfile(HISTORY_FILE):
        with open(HISTORY_FILE) as fh:
            return json.load(fh)
    return []


def save_history(messages):
    with open(HISTORY_FILE, "w") as fh:
        json.dump([m for m in messages if m.get("role") != "system"], fh)


def main():
    os.system("clear")
    tools = load_tools()
    history = load_history()
    messages = [{"role": "system", "content": SYSTEM}] + history
    print()

    if history:
        messages.append({"role": "user", "content": "Give a brief recap of our last conversation. Respond short."})
        try:
            content, _ = stream_chat(messages, [], spinner_label="Waking up...", spinner_color=GREEN)
            if content:
                messages.append({"role": "assistant", "content": content})
        except Exception:
            pass

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            save_history(messages)
            print(f"{RESET}\nBye.")
            break
        if not user_input:
            continue

        if user_input == "/reset":
            messages = [{"role": "system", "content": SYSTEM}]
            save_history(messages)
            os.system("clear")
            print()
            continue

        messages.append({"role": "user", "content": user_input})

        while True:
            try:
                content, tool_calls = stream_chat(messages, tools)
            except Exception as e:
                print(f"{RESET}[error] {e}")
                messages.pop()
                break

            msg = {"role": "assistant"}
            if content:
                msg["content"] = content
            if tool_calls:
                msg["tool_calls"] = tool_calls
            messages.append(msg)

            if not tool_calls:
                save_history(messages)
                break

            for tc in tool_calls:
                name = tc["function"]["name"]
                try:
                    args = json.loads(tc["function"]["arguments"])
                except json.JSONDecodeError:
                    args = {}
                print(f"{YELLOW}[{name}] {args.get('command', args)}{RESET}")
                result = run_tool(name, args)
                if "RELOAD_TOOLS" in result:
                    tools = load_tools()
                    result = result.replace("RELOAD_TOOLS", "Tool is now available.")
                print(f"{GRAY}{result[:200]}{'...' if len(result) > 200 else ''}{RESET}")
                messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result})


if __name__ == "__main__":
    main()
