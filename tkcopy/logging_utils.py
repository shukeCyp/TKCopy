"""Runtime logging helpers."""


def print_log(zh: str, en: str, **details):
    """Print a bilingual runtime log line."""
    suffix = ""
    if details:
        suffix = " | " + " ".join(f"{key}={value}" for key, value in details.items())
    print(f"[TKCopy] {zh} / {en}{suffix}", flush=True)
