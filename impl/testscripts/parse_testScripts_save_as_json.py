import requests
from bs4 import BeautifulSoup
import os

def save_test_scripts():
    # Create directory for JSON files
    json_dir = "test_script_json_files"
    if not os.path.exists(json_dir):
        os.makedirs(json_dir)
        print(f"\nCreated directory: {json_dir}")
    
    # Base URL
    base_url = "https://fhir.hl7.at/r4-core-80-include-testscripts"
    print(f"\n1. Accessing base URL: {base_url}/tests.html")
    
    # Get the main test page
    response = requests.get(f"{base_url}/tests.html")
    print(f"2. Response status code: {response.status_code}")
    
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Find all TestScript links
    for link in soup.find_all('a'):
        href = link.get('href')
        if href and href.startswith('TestScript-'):
            print(f"\n3. Found TestScript: {href}")
            
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
    print("Starting TestScript save process...")
    save_test_scripts()
    print("\nDone! Check 'test_script_json_files' directory for saved files.")

