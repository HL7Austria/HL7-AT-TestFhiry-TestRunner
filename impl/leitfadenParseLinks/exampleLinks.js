const http = require('http');
const https = require('https');
const { URL } = require('url');

function fetchPage(url) {
    return new Promise((resolve, reject) => {
        const lib = url.startsWith('https') ? https : http;
        lib.get(url, res => {
            let data = '';
            res.on('data', chunk => data += chunk);
            res.on('end', () => resolve(data));
        }).on('error', reject);
    });
}

function getBaseUrl(url) {
    return url.substring(0, url.lastIndexOf('/'));
}

function extractExampleLinksFromHtml(html, url) {
    // Finde Beginn der "Example:" Sektion
    const exampleStartRegex = /<h3[^>]*>\s*Example:.*?<\/h3>/i;
    const match = exampleStartRegex.exec(html);
    if (!match) {
        console.log("Keine 'Example:'-Sektion gefunden.");
        return [];
    }

    const startIndex = match.index + match[0].length;
    const restHtml = html.slice(startIndex);

    // Finde erstes </table> nach der Example-Überschrift
    const tableEndRegex = /<\/table>/i;
    const endMatch = tableEndRegex.exec(restHtml);
    const endIndex = endMatch ? startIndex + endMatch.index + endMatch[0].length : html.length;

    // Bereich zwischen <h3>Example:...</h3> und erstem </table>
    const exampleSection = html.slice(startIndex, endIndex);

    // Links extrahieren
    const linkRegex = /<a\s+[^>]*href="([^"]+)"[^>]*>/gi;
    const links = [];
    let linkMatch;

    while ((linkMatch = linkRegex.exec(exampleSection)) !== null) {
        let href = linkMatch[1];
        if (!href.includes("http")) {
            href = getBaseUrl(url) + "/" + href;
        }
        href = href.replace(/ /g, "%20");
        links.push(href);
    }

    return links;
}

async function extractExampleLinks(url) {
    try {
        const html = await fetchPage(url);
        const links = extractExampleLinksFromHtml(html, url);
        return links;
    } catch (err) {
        console.error("Fehler beim Abrufen oder Verarbeiten:", err.message);
        return [];
    }
}

// Beispielnutzung
extractExampleLinks('https://fhir.hl7.at/HL7-AT-FHIR-Core-R4/artifacts.html')
    .then(links => {
        console.log(`\n--- Gefundene Links in 'Example:'-Tabelle ---`);
        console.log(links.join("\n"));
    });
