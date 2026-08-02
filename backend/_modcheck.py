import os, re, glob
for f in sorted(glob.glob("app/models/*.py")):
    txt = open(f, encoding="utf-8").read()
    tabs = re.findall(r'__tablename__\s*=\s*["\']([^"\']+)', txt)
    print(os.path.basename(f), "=>", tabs)
