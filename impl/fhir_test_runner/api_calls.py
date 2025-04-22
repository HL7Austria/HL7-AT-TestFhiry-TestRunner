import requests

# pip install requests

# API-URL, zu der du eine Anfrage machen möchtest
base_url = "https://hapi.fhir.org/baseR4"
patient_nr = 0


### POST-Anfrage senden
def create_patient():
    global patient_nr
    url = base_url + "/Patient"
    headers = {
        "Accept": "application/fhir+json",
        "Prefer": "return=minimal"
    }

    body = {
        "resourceType": "Patient",
        "identifier": "HL7ATCorePatientExample01",
        "meta": {
            "profile": [
                "http://hl7.at/fhir/HL7ATCoreProfiles/4.0.1/StructureDefinition/at-core-patient"
            ]
        },
        "text": {
            "status": "generated",
            "div": "<div xmlns=\"http://www.w3.org/1999/xhtml\"><p class=\"res-header-id\"><b>Generated Narrative: Patient HL7ATCorePatientExample01</b></p><a name=\"HL7ATCorePatientExample01\"> </a><a name=\"hcHL7ATCorePatientExample01\"> </a><a name=\"HL7ATCorePatientExample01-en-US\"> </a><p style=\"border: 1px #661aff solid; background-color: #e6e6ff; padding: 10px;\">Max Mustermann  Male, DoB: 1900-01-01 ( Social Security number: 1234010100)</p><hr/><table class=\"grid\"><tr><td style=\"background-color: #f3f5da\" title=\"Other Ids (see the one above)\">Other Ids:</td><td colspan=\"3\"><ul><li>National unique individual identifier/GH:oeLdSEb0l+8kSdJWjOYyYmnYki0=</li><li>Patient internal identifier/0815</li></ul></td></tr><tr><td style=\"background-color: #f3f5da\" title=\"Ways to contact the Patient\">Contact Detail</td><td colspan=\"3\"><ul><li><a href=\"mailto:office@hl7.at\">office@hl7.at</a></li><li><a href=\"tel:+436501234567890\">+436501234567890</a></li><li>Landstrasse 1 Stock 9 Tür 42 Linz Oberösterreich 4020 AUT (home)</li></ul></td></tr><tr><td style=\"background-color: #f3f5da\" title=\"HL7® Austria FHIR® Core Extension for the religion (registered in Austria) of a patient.\r\nThe extension is used to encode the religious confession of a patient (only confessions registered in Austria). Furthermore, it uses the official [HL7 AT CodeSystem](https://termpub.gesundheit.gv.at:443/TermBrowser/gui/main/main.zul?loadType=CodeSystem&amp;loadName=HL7 AT ReligionAustria) for religion and is therefore aligned with the ELGA ValueSet, respectively.\">Patient Religion:</td><td colspan=\"3\"><ul><li>code: <span title=\"Codes:{https://termgit.elga.gv.at/CodeSystem/hl7-at-religionaustria 162}\">Pastafarianismus</span></li></ul></td></tr><tr><td style=\"background-color: #f3f5da\" title=\"The patient's legal status as citizen of a country.\">Patient Citizenship:</td><td colspan=\"3\"><ul><li>code: <span title=\"Codes:{https://termgit.elga.gv.at/CodeSystem/iso-3166-1-alpha-3 AUT}\">Österreich</span></li></ul></td></tr></table></div>"
        },
        "extension": [
            {
                "extension": [
                    {
                        "URL": "code",
                        "valueCodeableConcept": {
                            "coding": [
                                {
                                    "system": "https://termgit.elga.gv.at/CodeSystem/hl7-at-religionaustria",
                                    "code": "162",
                                    "display": "Pastafarianismus"
                                }
                            ]
                        }
                    }
                ],
                "URL": "http://hl7.at/fhir/HL7ATCoreProfiles/4.0.1/StructureDefinition/at-core-ext-patient-religion"
            },
            {
                "extension": [
                    {
                        "URL": "code",
                        "valueCodeableConcept": {
                            "coding": [
                                {
                                    "system": "https://termgit.elga.gv.at/CodeSystem/iso-3166-1-alpha-3",
                                    "code": "AUT",
                                    "display": "Österreich"
                                }
                            ]
                        }
                    }
                ],
                "URL": "http://hl7.org/fhir/StructureDefinition/patient-citizenship"
            }
        ],
        "identifier": [
            {
                "type": {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/v2-0203",
                            "code": "SS",
                            "display": "Social Security number"
                        }
                    ]
                },
                "system": "urn:oid:1.2.40.0.10.1.4.3.1",
                "value": "1234010100",
                "assigner": {
                    "display": "Dachverband der österreichischen Sozialversicherungsträger"
                }
            },
            {
                "type": {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/v2-0203",
                            "code": "NI",
                            "display": "National unique individual identifier"
                        }
                    ]
                },
                "system": "urn:oid:1.2.40.0.10.2.1.1.149",
                "value": "GH:oeLdSEb0l+8kSdJWjOYyYmnYki0=",
                "assigner": {
                    "display": "Bundesministerium für Inneres"
                }
            },
            {
                "type": {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/v2-0203",
                            "code": "PI",
                            "display": "Patient internal identifier"
                        }
                    ]
                },
                "system": "urn:oid:1.2.3.4.5",
                "value": "0815",
                "assigner": {
                    "display": "Ein GDA in Österreich"
                }
            }
        ],
        "name": [
            {
                "family": "Bodingbauer",
                "given": [
                    "Julia"
                ],
                "prefix": [
                    "DI"
                ]
            }
        ],
        "telecom": [
            {
                "system": "email",
                "value": "office@hl7.at",
                "use": "work"
            },
            {
                "system": "phone",
                "value": "+436501234567890",
                "use": "home"
            }
        ],
        "gender": "male",
        "birthDate": "1900-01-01",
        "address": [
            {
                "use": "home",
                "type": "both",
                "line": [
                    "Landstrasse 1 Stock 9 Tür 42"
                ],
                "_line": [
                    {
                        "extension": [
                            {
                                "URL": "http://hl7.org/fhir/StructureDefinition/iso21090-ADXP-streetName",
                                "valueString": "Landstrasse"
                            },
                            {
                                "URL": "http://hl7.org/fhir/StructureDefinition/iso21090-ADXP-houseNumber",
                                "valueString": "1"
                            },
                            {
                                "URL": "http://hl7.org/fhir/StructureDefinition/iso21090-ADXP-additionalLocator",
                                "valueString": "Stock 9 Tür 42"
                            },
                            {
                                "URL": "http://hl7.at/fhir/HL7ATCoreProfiles/4.0.1/StructureDefinition/at-core-ext-address-additionalInformation",
                                "valueString": "Lift vorhanden"
                            }
                        ]
                    }
                ],
                "city": "Linz",
                "state": "Oberösterreich",
                "postalCode": "4020",
                "country": "AUT"
            }
        ]
    }

    response = requests.post(url, json=body, headers=headers)

    # Antwort überprüfen
    if response.status_code == 201:
        print("Daten erfolgreich gesendet.")

        # Response-Header ausgeben

        # print("Response Headers:")
        # for header, value in response.headers.items():
        #    print(f"{header}: {value}")

        content_location = response.headers.get("Content-Location")
        print(content_location)
        patient_nr = content_location.split("/")[5]
        print(patient_nr)
        return response.json()

    else:
        print(f"Fehler: {response.status_code}")


### GET-Anfrage senden
def get_patient():
    url = base_url + "/Patient/" + patient_nr
    headers = {
        "Accept": "application/fhir+json"
    }

    response = requests.get(url)

    # Überprüfen, ob die Anfrage erfolgreich war (Statuscode 200)
    if response.status_code == 200:
        # JSON-Daten aus der Antwort extrahieren
        data = response.json()
        print(data)
        return data
    else:
        print(f"Fehler: {response.status_code}")


### UPDATE - Anfrage senden
def update_patient():
    url = base_url + "/Patient/" + patient_nr

    headers = {
        "Accept": "application/fhir+json",
        "Prefer": "return=representation"
    }

    body = {
        "resourceType": "Patient",
        "id": patient_nr,
        "identifier": "HL7ATCorePatientExample01",
        "meta": {
            "profile": [
                "http://hl7.at/fhir/HL7ATCoreProfiles/4.0.1/StructureDefinition/at-core-patient"
            ]
        },
        "extension": [
            {
                "extension": [
                    {
                        "URL": "code",
                        "valueCodeableConcept": {
                            "coding": [
                                {
                                    "system": "https://termgit.elga.gv.at/CodeSystem/hl7-at-religionaustria",
                                    "code": "162",
                                    "display": "Pastafarianismus"
                                }
                            ]
                        }
                    }
                ],
                "URL": "http://hl7.at/fhir/HL7ATCoreProfiles/4.0.1/StructureDefinition/at-core-ext-patient-religion"
            },
            {
                "extension": [
                    {
                        "URL": "code",
                        "valueCodeableConcept": {
                            "coding": [
                                {
                                    "system": "https://termgit.elga.gv.at/CodeSystem/iso-3166-1-alpha-3",
                                    "code": "AUT",
                                    "display": "Österreich"
                                }
                            ]
                        }
                    }
                ],
                "URL": "http://hl7.org/fhir/StructureDefinition/patient-citizenship"
            }
        ],
        "identifier": [
            {
                "type": {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/v2-0203",
                            "code": "SS",
                            "display": "Social Security number"
                        }
                    ]
                },
                "system": "urn:oid:1.2.40.0.10.1.4.3.1",
                "value": "1234010100",
                "assigner": {
                    "display": "Dachverband der österreichischen Sozialversicherungsträger"
                }
            },
            {
                "type": {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/v2-0203",
                            "code": "NI",
                            "display": "National unique individual identifier"
                        }
                    ]
                },
                "system": "urn:oid:1.2.40.0.10.2.1.1.149",
                "value": "GH:oeLdSEb0l+8kSdJWjOYyYmnYki0=",
                "assigner": {
                    "display": "Bundesministerium für Inneres"
                }
            },
            {
                "type": {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/v2-0203",
                            "code": "PI",
                            "display": "Patient internal identifier"
                        }
                    ]
                },
                "system": "urn:oid:1.2.3.4.5",
                "value": "0815",
                "assigner": {
                    "display": "Ein GDA in Österreich"
                }
            }
        ],
        "name": [
            {
                "family": "Bodingbauer",
                "given": [
                    "Julia"
                ],
                "prefix": [
                    "DI"
                ]
            }
        ],
        "telecom": [
            {
                "system": "email",
                "value": "office@hl7.at",
                "use": "work"
            },
            {
                "system": "phone",
                "value": "+436501234567890",
                "use": "home"
            }
        ],
        "gender": "female",
        "birthDate": "1930-03-06",
        "address": [
            {
                "use": "home",
                "type": "both",
                "line": [
                    "Landstrasse 5 Stock 3 Tür 26"
                ],
                "_line": [
                    {
                        "extension": [
                            {
                                "URL": "http://hl7.org/fhir/StructureDefinition/iso21090-ADXP-streetName",
                                "valueString": "Landstrasse"
                            },
                            {
                                "URL": "http://hl7.org/fhir/StructureDefinition/iso21090-ADXP-houseNumber",
                                "valueString": "5"
                            },
                            {
                                "URL": "http://hl7.org/fhir/StructureDefinition/iso21090-ADXP-additionalLocator",
                                "valueString": "Stock 3 Tür 26"
                            },
                            {
                                "URL": "http://hl7.at/fhir/HL7ATCoreProfiles/4.0.1/StructureDefinition/at-core-ext-address-additionalInformation",
                                "valueString": "Lift vorhanden"
                            }
                        ]
                    }
                ],
                "city": "Linz",
                "state": "Oberösterreich",
                "postalCode": "4020",
                "country": "AUT"
            }
        ]
    }

    response = requests.put(url, json=body, headers=headers)

    # Überprüfen, ob die Anfrage erfolgreich war
    if response.status_code == 200:
        print("Daten erfolgreich aktualisiert!")
        return response.json()
    else:
        print(f"Fehler bei der Aktualisierung: {response.status_code}")

    # Antwortstatus und Daten ausgeben
    print("Antwortstatuscode:", response.status_code)
    print("Antwortinhalt:", response.json())


def parse():
    pass


if __name__ == "__main__":
    print("\n*******************\n")
    create_patient()
    print("\n*******************\n")
    get_patient()
    print("\n*******************\n")
    update_patient()
    update_patient()
    print("\n*******************\n")
    get_patient()
