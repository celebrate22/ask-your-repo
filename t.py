from collections import Counter
from src.ask_repo.ingestion.walker import walk_repo

scan = walk_repo("/home/recoding/python-course")
files = {fn["file"] for fn in scan.functions}

print(len(scan.functions), "functions in", len(files), "files")
print(len(scan.skipped), "skipped:", Counter(s["error_type"] for s in scan.skipped))
print(Counter(f.split("/")[0] for f in (fn["file"] for fn in scan.functions)).most_common(5))
print("\n")
print("----SKIPPED FILES----")
for s in scan.skipped:
    print(s["file"], s["error_type"], s["message"])
