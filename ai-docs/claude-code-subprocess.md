# Claude Code Subprocess Reference

## Basic Usage

```bash
claude --print "Your prompt here"
```

`--print` (or `-p`) runs Claude Code non-interactively: sends the prompt, prints the response, and exits.

## Python Subprocess Call

```python
import subprocess

result = subprocess.run(
    ["claude", "--print", prompt],
    capture_output=True,
    text=True,
    timeout=120,
    cwd="/path/to/working/directory",
)

if result.returncode == 0:
    answer = result.stdout.strip()
else:
    error = result.stderr.strip()
```

## Key Parameters

| Parameter | Description |
|---|---|
| `--print` / `-p` | Non-interactive mode, prints response to stdout |
| `cwd` | Working directory - Claude Code can read/write files here |
| `timeout` | Recommended: 120s for complex tasks |

## Working Directory

Setting `cwd` gives Claude Code file access to that directory. For a notes assistant:
```python
result = subprocess.run(
    ["claude", "--print", "Liste alle Notizen auf"],
    cwd=os.path.expanduser("~/Projekte/Training2"),
    capture_output=True,
    text=True,
)
```

## System Prompt

Use `--system-prompt` to pass a system prompt:
```bash
claude --print --system-prompt "Du bist ein hilfreicher Assistent." "Frage hier"
```

Or in Python:
```python
result = subprocess.run(
    ["claude", "--print", "--system-prompt", system_prompt, user_prompt],
    capture_output=True,
    text=True,
    cwd=working_dir,
)
```

## Error Handling

- `returncode == 0`: Success, response in `stdout`
- `returncode != 0`: Error, details in `stderr`
- `subprocess.TimeoutExpired`: Command took too long
- Empty `stdout`: Claude had no response (treat as error)
