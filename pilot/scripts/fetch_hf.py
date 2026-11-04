import json, sys, urllib.request, concurrent.futures as cf, os
REPO = "adlnk/petri-synthetic-transcripts"
DST = sys.argv[1]
api = json.load(urllib.request.urlopen(f"https://huggingface.co/api/datasets/{REPO}", timeout=60))
files = [s["rfilename"] for s in api["siblings"]]
files = [f for f in files if f in ("README.md","data/corpus_index.json","data/manifest.json","metadata/croissant.json","data/synthetic_corpus_seeds.yaml","data/dimension_guided_seeds.yaml") or f.startswith("data/transcripts/")]
def get(f):
    out = os.path.join(DST, f)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    url = f"https://huggingface.co/datasets/{REPO}/resolve/main/{f}"
    with urllib.request.urlopen(url, timeout=120) as r, open(out, "wb") as w:
        w.write(r.read())
    return os.path.getsize(out)
with cf.ThreadPoolExecutor(8) as ex:
    sizes = list(ex.map(get, files))
print("files", len(files), "total_bytes", sum(sizes), "max_bytes", max(sizes), "min_bytes", min(sizes))
