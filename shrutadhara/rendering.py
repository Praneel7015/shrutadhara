"""Literal rendering for untrusted dialogue and model text.

JSON keeps the original text. Markdown controls and URL punctuation are escaped
here; only the application builds active anchors and evidence links.
"""

import re
import string

_PUNCTUATION = re.compile("([" + re.escape(string.punctuation) + "])")


def literal(text: str, *, single_line: bool = False) -> str:
    value = text.replace("\r\n", "\n").replace("\r", "\n")
    if single_line:
        value = value.replace("\n", " ")
    return _PUNCTUATION.sub(r"\\\1", value)
