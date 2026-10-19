"""Sanitising of user-submitted free text (Security doc: input validation).

We store plain text. Markup is stripped (not escaped), so a client that renders
the string as text, or even as HTML, cannot be made to run injected script.
"""
import html
import re
import unicodedata

_TAG = re.compile(r"<[^>]*>?")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_SPACES = re.compile(r"[ \t]+")
_BLANK_LINES = re.compile(r"\n{3,}")


def clean_text(value: str) -> str:
    value = unicodedata.normalize("NFC", value)
    value = html.unescape(value)       # turn &lt;script&gt; back into <script> so it is stripped too
    value = _TAG.sub("", value)
    value = _CONTROL.sub("", value)
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    value = _SPACES.sub(" ", value)
    value = _BLANK_LINES.sub("\n\n", value)
    return value.strip()


def display_name(full_name: str | None) -> str:
    """Public-facing name: first name plus last initial ("Priya S.")."""
    parts = (full_name or "").split()
    if not parts:
        return "A walker"
    if len(parts) == 1:
        return parts[0]
    return f"{parts[0]} {parts[-1][0].upper()}."
