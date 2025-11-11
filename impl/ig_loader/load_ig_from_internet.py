import requests
from bs4 import BeautifulSoup
import os
import json
import re


def read_config_file():
    with open("../config.json", "r") as f:
        config = json.load(f)
    url = config["url"]
    return url

def save_example_instances():
    # Use the specific directory path
    json_dir = os.path.join("..", "Example_Instances")

    # Create directory if it doesn't exist
    os.makedirs(json_dir, exist_ok=True)

    # Base URL
    base_url = read_config_file()

    # Get the artifacts page
    response = requests.get(f"{base_url}/artifacts.html")

    soup = BeautifulSoup(response.text, 'html.parser')

    example_text = soup.find(
        lambda tag: tag.name in ["h2", "h3", "h4", "h5", "h6"]
                    and re.search(r"Example:\s*Example Instances", tag.get_text(strip=True), re.I)
    )

    links = []
    if example_text:
        section = example_text.find_next(["div", "table", "p"])

        while section and section.name not in ["div", "table"]:
            section = section.find_next(["div", "table", "script", "style"])

        if section and section.name in ["div", "table"]:
            for a in section.find_all("a", href=True):
                links.append(a["href"])

    save_links(links, json_dir, base_url)


def save_profiles():
    # Use the specific directory path
    json_dir = os.path.join("..", "Profiles")

    # Create directory if it doesn't exist
    os.makedirs(json_dir, exist_ok=True)

    # Base URL
    base_url = read_config_file()

    # Get the artifacts page
    response = requests.get(f"{base_url}/artifacts.html")

    soup = BeautifulSoup(response.text, 'html.parser')

    profile_headers = soup.find_all(
        lambda tag: tag.name in ["h2", "h3", "h4", "h5", "h6"]
                    and re.search(r"profiles", tag.get_text(strip=True), re.I)
    )

    links = []
    for header in profile_headers:
        section = header.find_next(["div", "table", "p"])

        while section and section.name not in ["div", "table"]:
            section = section.find_next(["div", "table", "script", "style"])

        if section and section.name in ["div", "table"]:
            for a in section.find_all("a", href=True):
                links.append(a["href"])

    links = list(dict.fromkeys(links))

    save_links(links, json_dir, base_url)



def save_links(links, json_dir, url):
    for link in links:
        json_url = f"{url}/{link.replace('.html', '.json')}"
        json_response = requests.get(json_url)

        if json_response.status_code == 200:
            filename = link.replace('.html', '.json')
            filepath = os.path.join(json_dir, filename)
            print(f"Saving to file: {filepath}")

            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(json_response.text)
            print("File saved successfully!")
        else:
            print(f"Failed to get JSON content from {json_url}")


def save_test_scripts():
    # Use the specific directory path
    json_dir = os.path.join("..", "Test_Scripts")
    print(f"\nUsing directory: {json_dir}")
    os.makedirs(json_dir, exist_ok=True)
    # Base URL
    base_url = read_config_file()

    # Get the main test page
    response = requests.get(f"{base_url}/tests.html")

    soup = BeautifulSoup(response.text, 'html.parser')

    # Find all TestScript links
    for link in soup.find_all('a'):
        href = link.get('href')
        if href and href.startswith('TestScript-'):

            # Convert to direct JSON URL
            json_url = f"{base_url}/{href.replace('.html', '.json')}"

            # Get JSON content directly
            json_response = requests.get(json_url)

            if json_response.status_code == 200:
                # Get filename and create full path
                filename = href.replace('.html', '.json')
                filepath = os.path.join(json_dir, filename)

                # Save JSON content to file
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(json_response.text)
                print("File saved successfully!")
            else:
                print(f"Failed to get JSON content from {json_url}")


if __name__ == "__main__":
    save_example_instances()
    save_profiles()
    save_test_scripts()
