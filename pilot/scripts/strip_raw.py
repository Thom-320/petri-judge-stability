"""Derive the public scores-only pilot file from the raw judge outputs.

Usage: python3 -I pilot/scripts/strip_raw.py <raw judgments.jsonl> <out scores.jsonl>

Drops the judge's generated text (`content`) and keeps ids, judge, repeat, status, finish reason,
token usage, output length and the parsed scores, which is everything analysis/ reads.
The raw file stays out of the public repository .
"""
import json
import sys

DROP = {"content"}

src, dst = sys.argv[1], sys.argv[2]
n = 0
with open(src, encoding="utf-8") as f, open(dst, "w", encoding="utf-8") as g:
    for line in f:
        if line.strip():
            r = json.loads(line)
            g.write(json.dumps({k: v for k, v in r.items() if k not in DROP}, ensure_ascii=False) + "\n")
            n += 1
print(f"{n} records -> {dst}")
