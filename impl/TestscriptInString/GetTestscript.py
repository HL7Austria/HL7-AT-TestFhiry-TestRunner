import json
import requests

# Load config file
try:
    with open("config.json", "r") as file:
        config = json.load(file)
except FileNotFoundError:
    print("Error: 'config.json' file not found.")
    exit(1)
except json.JSONDecodeError as e:
    print(f"Error: Failed to parse 'config.json': {e}")
    exit(1)

# Use the first IG URL as base URL
base_url = config["IG"][0]

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
