from fhirpy import SyncFHIRClient


# Verbindung zum öffentlichen HAPI FHIR-Server
client = SyncFHIRClient("https://hapi.fhir.org/baseR4")

# Patienten suchen, deren Nachname "Mustermann" ist
#patients = client.resources("Patient").search(family="Mustermann").fetch()

# Ergebnisse durchgehen
#for patient in patients:
#    print(patient["id"], patient["name"])

# Einen neuen Patienten erstellen
new_patient = client.resource(
    "Patient",
    name=[{"family": "Honeder", "given": ["Julia"]}],
    gender="male",
    birthDate="1985-05-12"
)

# Zum Server hochladen
new_patient.save()
print(f"Patient gespeichert: {new_patient.id}")

# Patienten abrufen
patient = client.resources("Patient").search(family="Honeder").fetch()#.first()

for p in patient:
        name = p["name"][0]
        id = p["id"]
        print(f"ID:{id}")
        print(f"Nachname: {name['family']}")
        print(f"Vorname: {name['given'][0]}")








