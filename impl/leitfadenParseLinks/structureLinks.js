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

function extractLinksFromHtml(html, url) {
    const sectionPattern = /<a\s+name="[1-9]+">\s*<\/a>\s*<h3>\s*Structures: ([A-Za-z ]+)\s*<\/h3>/gi;
    const sectionEnd = /<a\s+.*?>\s*<\/a>\s*<h3>\s*(?!Structures: )[A-Za-z: ]+\s*<\/h3>/gi;

    const sectionMatches = [...html.matchAll(sectionPattern)].map(m => ({ index: m.index, type: 'start', title: m[1].trim() }));
    const endMatches = [...html.matchAll(sectionEnd)].map(m => ({ index: m.index, type: 'end' }));

    const allMarkers = [...sectionMatches, ...endMatches].sort((a, b) => a.index - b.index);

    const results = [];

    for (let i = 0; i < allMarkers.length; i++) {
        const marker = allMarkers[i];

        if (marker.type === 'start') {
            const startIndex = marker.index;
            const title = marker.title;

            let endIndex = html.length;
            for (let j = i + 1; j < allMarkers.length; j++) {
                if (allMarkers[j].type === 'start' || allMarkers[j].type === 'end') {
                    endIndex = allMarkers[j].index;
                    break;
                }
            }

            const sectionContent = html.slice(startIndex, endIndex);

            const linkRegex = /<a\s+[^>]*href="([^"]+)"[^>]*>/gi;
            const links = [];
            let match;

            while ((match = linkRegex.exec(sectionContent)) !== null) {
                let href = match[1];

                if (!href.includes("http")) {
                    href = getBaseUrl(url) + "/" + href;
                }

                href = href.replace(/ /g, "%20");
                links.push(href);
            }

            results.push([title, links]);
        }
    }

    console.log(`Es wurden ${results.length} passende Sektionen gefunden.`);
    return results;
}

async function extractLinksFromSection(url) {
    try {
        const html = await fetchPage(url);
        const sections = extractLinksFromHtml(html, url);
        return sections;
    } catch (err) {
        console.error("Fehler beim Abrufen oder Verarbeiten:", err.message);
        return [];
    }
}

extractLinksFromSection('https://fhir.hl7.at/HL7-AT-FHIR-Core-R4/artifacts.html')
    .then(sections => {
        sections.forEach(([title, links], i) => {
            console.log(`\n--- Sektion ${i + 1}: ${title} ---`);
            console.log(links.join("\n"));
        });
    });
