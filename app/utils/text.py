import re
import hashlib

def normalize_text(s: str) -> str:
    s = s or ""
    s = re.sub(r"\s+", " ", s).strip()
    return s

def text_hash(s: str) -> str:
    s = normalize_text(s)[:2000]
    return hashlib.sha256(s.encode("utf-8")).hexdigest()
