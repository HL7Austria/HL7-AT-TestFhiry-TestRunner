import argparse
import requests
from bs4 import BeautifulSoup
import os
import json
import re
from pathlib import Path
from urllib.parse import urljoin

BASE_DIR = Path(__file__).resolve().parent.parent


def read_config_file(config_path=None):
    if config_path is None:
        config_path = BASE_DIR / "config.json"
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except FileNotFoundError:
        print(f"Error: config.json not found at {config_path}")
        raise
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {config_path}: {e}")
        raise

    url = config.get("url")
    if not url:
        raise ValueError(f"'url' key not found in {config_path}")
    resource_path = config.get("path", "")
    return url, resource_path

def save_example_instances(config_path=None):
    # Base URL and resource path
    base_url, resource_path = read_config_file(config_path)

    # Use the specific directory path
    if resource_path:
        json_dir = Path(resource_path) / "Example_Instances"
    else:
        json_dir = BASE_DIR / "Example_Instances"

    # Create directory if it doesn't exist
    os.makedirs(json_dir, exist_ok=True)

    # Get the artifacts page
    artifacts_url = f"{base_url}/artifacts.html"
    response = requests.get(artifacts_url, timeout=30)
    soup = BeautifulSoup(response.text, 'html.parser')

    # Newer IG templates render the artifacts table client-side from a JS data file;
    # example instances are the rows of the "-ex-example" group (artifacts.html#-ex-example)
    links = [
        row["u"] for row in load_artifacts_table_rows(soup, artifacts_url)
        if row.get("u") and row.get("gid") == "-ex-example"
    ]

    # Older IG templates render the examples in their own section with header and table
    example_text = soup.find(
        lambda tag: tag.name in ["h2", "h3", "h4", "h5", "h6"]
                    and bool(re.search(r"Example:\s*Example Instances", tag.get_text(strip=True), re.I))
    )

    if example_text:
        section = example_text.find_next(["div", "table", "p"])

        while section and section.name not in ["div", "table"]:
            section = section.find_next(["div", "table", "script", "style"])

        if section and section.name in ["div", "table"]:
            for a in section.find_all("a", href=True):
                links.append(a["href"])

    links = list(dict.fromkeys(links))
    print(f"Found {len(links)} example instances on {artifacts_url}")

    save_links(links, json_dir, base_url)


def save_profiles(config_path=None):
    # Base URL and resource path
    base_url, resource_path = read_config_file(config_path)

    # Use the specific directory path
    if resource_path:
        json_dir = Path(resource_path) / "Profiles"
    else:
        json_dir = BASE_DIR / "Profiles"

    # Create directory if it doesn't exist
    os.makedirs(json_dir, exist_ok=True)

    # Get the artifacts page
    artifacts_url = f"{base_url}/artifacts.html"
    response = requests.get(artifacts_url, timeout=30)
    soup = BeautifulSoup(response.text, 'html.parser')

    # Profiles reference the IG's extensions, so the validator needs both
    # (e.g. "Structures: Resource Profiles", "Structures: Extension Definitions")
    category_pattern = re.compile(r"profiles|extension definitions", re.I)

    # Newer IG templates render the artifacts table client-side from a JS data file,
    # grouped by category
    links = [
        row["u"] for row in load_artifacts_table_rows(soup, artifacts_url)
        if row.get("u") and category_pattern.search(row.get("g", ""))
    ]

    # Older IG templates render one section per category, each with its own header and table
    profile_headers = soup.find_all(
        lambda tag: tag.name in ["h2", "h3", "h4", "h5", "h6"]
                    and bool(category_pattern.search(tag.get_text(strip=True)))
    )

    for header in profile_headers:
        section = header.find_next(["div", "table", "p"])

        while section and section.name not in ["div", "table"]:
            section = section.find_next(["div", "table", "script", "style"])

        if section and section.name in ["div", "table"]:
            for a in section.find_all("a", href=True):
                links.append(a["href"])

    links = list(dict.fromkeys(links))
    print(f"Found {len(links)} profiles and extensions on {artifacts_url}")

    save_links(links, json_dir, base_url)


def load_artifacts_table_rows(soup, page_url):
    # Rows of the client-side artifacts table, read from the script that holds its data
    # (window.artifactsTableData = {<lang>: {"rows": [{"g": <category>, "u": <page>, ...}]}})
    script = soup.find("script", src=re.compile(r"artifacts-table-data\.js"))
    if not script:
        return []

    data_url = urljoin(page_url, script["src"])
    try:
        response = requests.get(data_url, timeout=30)
        response.raise_for_status()
        js = response.text
        data = json.loads(js[js.index("=") + 1:].strip().rstrip(";"))
    except (requests.RequestException, ValueError) as e:
        print(f"Error reading artifacts table data from {data_url}: {e}")
        return []

    # Pick the language block the same way the page does, based on <html lang="...">
    lang = soup.html.get("lang", "") if soup.html else ""
    block = data.get(lang) or data.get(lang.split("-")[0]) or next(iter(data.values()), {})
    return block.get("rows", [])


def save_links(links, json_dir, url):
    for link in links:
        json_url = f"{url}/{link.replace('.html', '.json')}"
        try:
            json_response = requests.get(json_url, timeout=30)
        except requests.RequestException as e:
            print(f"Error downloading {json_url}: {e}")
            continue

        if json_response.status_code == 200:
            filename = link.replace('.html', '.json')
            filepath = os.path.join(json_dir, filename)
            print(f"Saving to file: {filepath}")

            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(json_response.text)
            print("File saved successfully!")
        else:
            print(f"Failed to get JSON content from {json_url} (status {json_response.status_code})")


def save_test_scripts(config_path=None):
    # Base URL and resource path
    base_url, resource_path = read_config_file(config_path)

    # Use the specific directory path
    if resource_path:
        json_dir = Path(resource_path) / "Test_Scripts"
    else:
        json_dir = BASE_DIR / "Test_Scripts"
    print(f"\nUsing directory: {json_dir}")
    os.makedirs(json_dir, exist_ok=True)

    # Get the main test page
    response = requests.get(f"{base_url}/tests.html", timeout=30)
    soup = BeautifulSoup(response.text, 'html.parser')

    # Find all TestScript links
    links = [
        a["href"] for a in soup.find_all("a", href=True)
        if str(a["href"]).startswith("TestScript-")
    ]

    save_links(links, json_dir, base_url)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download IG resources from the internet")
    parser.add_argument("--config", default=None, help="Path to config.json")
    args = parser.parse_args()

    save_example_instances(args.config)
    save_profiles(args.config)
    save_test_scripts(args.config)
