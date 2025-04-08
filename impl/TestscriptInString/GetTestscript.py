import requests

#URL
base_url = "https://build.fhir.org/"

# Dateinamen der TestScript-Beispiele
testscript_files = [
    "testscript-example.xml",
    "testscript-example-history.xml",
    "testscript-example-multisystem.xml",
    "testscript-example-readtest.xml",
    "testscript-example-readcommon.xml",
    "testscript-example-search.xml",
    "testscript-example-update.xml"
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


print(testscript_contents["testscript-example-history.xml"])
