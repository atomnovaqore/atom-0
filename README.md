# atom-0

Dead-simple chat CLI for local Qwen 3.5 9B.

## Run

```bash
python3 chat.py
```

## Config

| Env var     | Default                                         |
|-------------|--------------------------------------------------|
| `LLM_URL`   | `http://localhost:19400/v1/chat/completions`     |
| `LLM_MODEL` | `qwen3.5`                                        |

## Remote (via SSH tunnel)

Forward the Pi's LLM port to localhost:

```bash
ssh -f -N -L 19400:localhost:19400 atom@192.168.1.143 -i ~/.ssh/atom-aws
python3 chat.py
```
