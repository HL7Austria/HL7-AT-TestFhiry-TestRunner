import requests
from bs4 import BeautifulSoup
import os

def save_example_instances():
    # Use the specific directory path
    json_dir = "impl/testscripts/Example_Instances/example_instances_json"
    print(f"\nUsing directory: {json_dir}")
    
    # Create directory if it doesn't exist
    os.makedirs(json_dir, exist_ok=True)
    
    # Base URL
    base_url = "https://fhir.hl7.at/r4-core-80-include-testscripts"
    print(f"\n1. Accessing artifacts URL: {base_url}/artifacts.html")
    
    # Get the artifacts page
    response = requests.get(f"{base_url}/artifacts.html")
    print(f"2. Response status code: {response.status_code}")
    
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Find all example instance links in the table
    for link in soup.find_all('a'):
        href = link.get('href')
        if href and (href.startswith('Patient-') or href.startswith('Organization-')):
            print(f"\n3. Found Example Instance: {href}")
            
            # Convert to JSON URL
            json_url = f"{base_url}/{href.replace('.html', '.json.html')}"
            print(f"4. Accessing JSON URL: {json_url}")
            
            # Get JSON content
            json_response = requests.get(json_url)
            print(f"5. Response status code: {json_response.status_code}")
            
            if json_response.status_code == 200:
                # Parse JSON page
                json_soup = BeautifulSoup(json_response.text, 'html.parser')
                json_content = json_soup.find('pre')
                
                if json_content:
                    # Get filename and create full path
                    filename = href.replace('.html', '.json')
                    filepath = os.path.join(json_dir, filename)
                    print(f"6. Saving to file: {filepath}")
                    
                    # Save JSON content to file
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(json_content.get_text())
                    print("7. File saved successfully!")
                else:
                    print("6. No JSON content found in response")
            else:
                print("5. Failed to get JSON content")

if __name__ == "__main__":
    print("Starting Example Instances save process...")
    save_example_instances()
    print("\nDone! Check 'impl/testscripts/example_instances' directory for saved files.")