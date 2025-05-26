import { ExampleInstance } from './ExampleInstance.js';

const link = "https://fhir.hl7.at/HL7-AT-FHIR-Core-R4/Organization-HL7ATCoreOrganizationExample02-MultipleVPNR.html";

const instance = new ExampleInstance();
instance.init(link).then(() => {
    console.log("\n");
    console.log("ID:", instance.id);
    console.log("Ressourcentyp:", instance.resourceType);
    console.log("Name:", instance.name);
});
