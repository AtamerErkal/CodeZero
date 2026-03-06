import sys

filepath = "e:/3. projects/CodeZero/hospital_server_v1.py"
with open(filepath, "r", encoding="utf-8") as f:
    text = f.read()

text = text.replace('ROOT / "ui" / "patient_app_v7.html",', 'ROOT / "ui" / "patient_app_v8.html",\n        ROOT / "ui" / "patient_app_v7.html",')

patch = '''from fastapi.staticfiles import StaticFiles
docs_dir = ROOT / "docs"
if docs_dir.exists():
    app.mount("/docs", StaticFiles(directory=str(docs_dir)), name="docs")

NAT_FLAG'''
text = text.replace('NAT_FLAG', patch, 1)

with open(filepath, "w", encoding="utf-8") as f:
    f.write(text)
print("patch successful")
