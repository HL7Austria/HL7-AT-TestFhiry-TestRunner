const fs = require('fs');
const path = require('path');

function printSection(title, items) {
    console.log(`\n=== ${title} (${items.length}) ===`);
    items.forEach((item, i) => {
        console.log(`\n#${i + 1}:`);
        console.dir(item, { depth: null });
    });
}

const filePath = path.join(__dirname, 'testScript.json');
const testScript = JSON.parse(fs.readFileSync(filePath, 'utf-8'));

const setupActions = testScript.setup?.action || [];
const setupOperations = setupActions.filter(a => a.operation).map(a => a.operation);
const setupAsserts = setupActions.filter(a => a.assert).map(a => a.assert);

const tests = testScript.test || [];
const testOperations = [];
const testAsserts = [];

tests.forEach(test => {
    (test.action || []).forEach(action => {
        if (action.operation) testOperations.push(action.operation);
        if (action.assert) testAsserts.push(action.assert);
    });
});

const teardownActions = testScript.teardown?.action || [];
const teardownOperations = teardownActions.filter(a => a.operation).map(a => a.operation);

const fixtures = testScript.fixture || [];

printSection('Setup-Operationen', setupOperations);
printSection('Setup-Assertions', setupAsserts);
printSection('Test-Operationen', testOperations);
printSection('Test-Assertions', testAsserts);
printSection('Teardown-Operationen', teardownOperations);
printSection('Fixtures', fixtures);
