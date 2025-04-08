from fhir.resources.patient import Patient
import json
import requests

URL = "https://hapi.fhir.org/baseR5/Patient/"

# Header for the HTTP request
HEADERS = {
    "Content-Type": "application/fhir+json",  # content type for FHIR Data
    "Accept": "application/fhir+json"  # We expect FHIR data in response
}


#----------------------------- PARSE DATA FROM JSON ----------------------------------------
# Parse Data from JSON
json_data = '{"resourceType": "Patient", "id": "example", "name": [{"family": "Bodingbauer", "given": ["Julia"]}]}'
patient = Patient.parse_raw(json_data)

print(patient.name[0].family)  # Output: Julia
#----------------------------- PARSE DATA FROM JSON ----------------------------------------

#----------------------------- CREATE PATIENT ----------------------------------------
# Create patient
new_patient = Patient(
    resourceType="Patient",  # Type of resource
    id="new-example",  # ID for new Patient
    name=[{
        "family": "ASDFASDF",
        "given": ["JULIA BBB"]
    }],
    gender="female",
    birthDate="1985-05-12",
    address=[{
        "use": "home",
        "line": ["123 Main Street"],
        "city": "Somewhere",
        "state": "SomeState",
        "postalCode": "12345",
        "country": "Country"
    }],
    telecom=[{
        "system": "phone",
        "value": "+1234567890",
        "use": "home"
    }]
)

# Convert the patient object to JSON
patient_json = new_patient.model_dump_json()

# send post request to create patient
response = requests.post(URL, data=patient_json, headers=HEADERS)

# check if request was ok
if response.status_code == 201:
    print("Patient successfully created!")
    print(response.json())  # Output of the server response
else:
    print(f"Error: {response.status_code}")
#----------------------------- CREATE PATIENT ----------------------------------------



#----------------------------- GET PATIENT ----------------------------------------
patient_id = response.json()["id"]
get_url = URL + patient_id

response = requests.get(get_url, headers=HEADERS)

if response.status_code == 200:
    patient_data = response.json()
    print("Patient found:")
    print(patient_data["name"][0]["given"][0], patient_data["name"][0]["family"])
else:
    print(f"Error while fetching: {response.status_code}")
# ----------------------------- GET PATIENT ----------------------------------------


# ----------------------------- UPDATE PATIENT ----------------------------------------
# Get Patient Data
patient_id = response.json()["id"]
get_url = URL + patient_id

response = requests.get(get_url, headers=HEADERS)

if response.status_code == 200:
    patient_data = response.json()

    #changes
    patient_data["name"][0]["given"][0] = "Julia-Geändert"

    # convert json to string
    updated_patient_json = json.dumps(patient_data)

    # PUT Request
    update_response_failed = requests.put(get_url, data=updated_patient_json, headers=HEADERS) # update needs to be done 2 times
    update_response = requests.put(get_url, data=updated_patient_json, headers=HEADERS)


    if update_response.status_code in [200, 201]:
        print("Patient successfully updated!")
    else:
        print(f"Update Error: {update_response.status_code}")
else:
    print(f"Error while calling Update: {response.status_code}")

# ----------------------------- UPDATE PATIENT ----------------------------------------


# ----------------------------- DELETE PATIENT ----------------------------------------
delete_url = URL + patient_id
delete_response = requests.delete(delete_url, headers=HEADERS)
delete_response = requests.delete(delete_url, headers=HEADERS)# delete needs to be done 2 times


if delete_response.status_code == 200:
    print("Patient successfully deleted")
else:
    print(f"Delete Error: {delete_response.status_code}")

# ----------------------------- DELETE PATIENT ----------------------------------------
