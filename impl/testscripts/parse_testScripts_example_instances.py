import requests
from bs4 import BeautifulSoup
import os
import json


def read_config_file():
    with open("../config.json", "r") as f:
        config = json.load(f)
    url = config["url"]
    return url


def save_example_instances():
    # Use the specific directory path
    json_dir = "Example_Instances"

    # Create directory if it doesn't exist
    os.makedirs(json_dir, exist_ok=True)

    # Base URL
    base_url = read_config_file()

    # Get the artifacts page
    response = requests.get(f"{base_url}/artifacts.html")

    soup = BeautifulSoup(response.text, 'html.parser')

    # Find all example instance links in the table
    for link in soup.find_all('a'):
        href = link.get('href')
        if href and (href.startswith('Patient-') or href.startswith('Organization-')):

            # Convert to JSON URL
            json_url = f"{base_url}/{href.replace('.html', '.json.html')}"

            # Get JSON content
            json_response = requests.get(json_url)

            if json_response.status_code == 200:
                # Parse JSON page
                json_soup = BeautifulSoup(json_response.text, 'html.parser')
                json_content = json_soup.find('pre')

                if json_content:
                    # Get filename and create full path
                    filename = href.replace('.html', '.json')
                    filepath = os.path.join(json_dir, filename)
                    print(f"Saving to file: {filepath}")

                    # Save JSON content to file
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(json_content.get_text())
                    print("File saved successfully!")
                else:
                    print("No JSON content found in response")
            else:
                print("Failed to get JSON content")


def save_test_scripts():
    # Use the specific directory path
    json_dir = "TestScripts"
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

            # Convert to JSON URL
            json_url = f"{base_url}/{href.replace('.html', '.json.html')}"

            # Get JSON content
            json_response = requests.get(json_url)

            if json_response.status_code == 200:
                # Parse JSON page
                json_soup = BeautifulSoup(json_response.text, 'html.parser')
                json_content = json_soup.find('pre')

                if json_content:
                    # Get filename and create full path
                    filename = href.replace('.html', '.json')
                    filepath = os.path.join(json_dir, filename)

                    # Save JSON content to file
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(json_content.get_text())
                    print("File saved successfully!")
                else:
                    print("No JSON content found in response")
            else:
                print("Failed to get JSON content")


if __name__ == "__main__":
    save_example_instances()
    save_test_scripts()
