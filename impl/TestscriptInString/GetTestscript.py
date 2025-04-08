import requests

#URL
base_url = "https://build.fhir.org/"

# Dateinamen der TestScript-Beispiele
testscript_files = [
    "testscript-example.json",
    "testscript-example-history.json",
    "testscript-example-multisystem.json",
    "testscript-example-readtest.json",
    "testscript-example-readcommon.json",
    "testscript-example-search.json",
    "testscript-example-update.json"
]

testscript_contents = {}

# Alle Inhalte per HTTP abrufen und als String speichern

for filename in testscript_files:
    url = base_url + filename
    response = requests.get(url)
    if response.status_code == 200:
        testscript_contents[filename] = response.text
    else:
        print(f"Fehler beim Laden von {filename}: Status {response.status_code}")


print(testscript_contents["testscript-example-history.json"])
