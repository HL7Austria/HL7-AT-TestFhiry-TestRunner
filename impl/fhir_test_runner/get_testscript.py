import json
import requests


from configuration.read_config_file import read_config_file

# read
base_url = read_config_file("IG")

# List of TestScript filenames
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

# Download each file via HTTP and store content as string
for filename in testscript_files:
    url = base_url + filename
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise exception for non-2xx responses
        testscript_contents[filename] = response.text
    except requests.exceptions.RequestException as e:
        print(f"Failed to load '{filename}' from '{url}': {e}")

# Print one example to verify
print(testscript_contents.get("testscript-example-multisystem.json", "Error: File could not be loaded. ."))
