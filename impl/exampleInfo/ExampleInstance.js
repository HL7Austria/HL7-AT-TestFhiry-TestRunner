export class ExampleInstance {
    resourceType;
    text;
    id;
    name;

    constructor() {
        this.id = "";
        this.text = "";
        this.resourceType = "";
        this.name = "";
    }

    #convertLink(url) {
        if (url.endsWith(".html") && !url.endsWith(".json")) {
            if (url.endsWith(".json.html")) {
                return url.replace(/\.json\.html$/, ".json");
            }
            return url.replace(/\.html$/, ".json");
        }
        return url;
    }

    #extractName(json) {
        const nameField = json.name;
        if (!nameField) return "";

        if (typeof nameField === "string") {
            return nameField;
        }

        if (Array.isArray(nameField) && typeof nameField[0] === "object") {
            const nameObj = nameField[0];
            const given = Array.isArray(nameObj.given) ? nameObj.given[0] : nameObj.given ?? "";
            const family = nameObj.family ?? "";
            const prefix = Array.isArray(nameObj.prefix) ? nameObj.prefix.join(" ") + " " : "";
            return `${prefix}${given} ${family}`.trim();
        }

        return "";
    }

    init(url) {
        const link = this.#convertLink(url);
        return fetch(link)
            .then(response => {
                if (!response.ok) throw new Error("HTTP-Fehler " + response.status);
                return response.json();
            })
            .then(data => {
                this.id = data.id ?? "";
                this.text = data.text?.div ?? "";
                this.resourceType = data.resourceType ?? "";
                this.name = this.#extractName(data);
            })
            .catch(error => {
                console.error("Fehler beim Laden:", error);
            });
    }
}
