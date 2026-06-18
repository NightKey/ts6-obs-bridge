import sys
from os import path
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(path.join(root_dir, "src")))


from bridge import Bridge

print("[SANITY TEST] Done")