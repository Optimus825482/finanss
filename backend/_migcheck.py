import glob, re, os

files = sorted(glob.glob("alembic/versions/*.py"))
m = {}
for f in files:
    txt = open(f, encoding="utf-8").read()
    rev = re.search(r'^revision\s*=\s*["\']([^"\']+)', txt, re.M)
    down = re.search(r'^down_revision\s*=\s*["\']([^"\']+)', txt, re.M)
    d = down.group(1) if down else None
    m[rev.group(1) if rev else "? " + os.path.basename(f)] = {
        "file": os.path.basename(f),
        "down": d,
        "create_table": txt.count("op.create_table"),
        "has_create_all": "create_all" in txt,
    }
print(f"{'rev':<18} {'down':<18} ct  ca  file")
for rev, info in m.items():
    print(f"{rev:<18} {str(info['down']):<18} {info['create_table']:<3} {str(info['has_create_all']):<5} {info['file']}")
