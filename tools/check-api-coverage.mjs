// Maintainer-only drift check. Reads a public API reference, never server source.
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';

const [catalogPath, examplesPath] = process.argv.slice(2);
if (!catalogPath || !examplesPath) {
  throw new Error('Usage: node tools/check-api-coverage.mjs /path/to/api-docs.js /path/to/api-examples.js');
}
const [catalogSource, exampleSource, fixtureText] = await Promise.all([
  readFile(catalogPath, 'utf8'), readFile(examplesPath, 'utf8'),
  readFile(new URL('../tests/fixtures/api-v1.json', import.meta.url), 'utf8'),
]);
const end = catalogSource.indexOf('  const runtime = {');
assert.ok(end > 0, 'Public catalog boundary changed; review before updating this tool.');
const context = vm.createContext({});
vm.runInContext(exampleSource, context, {timeout: 1000});
vm.runInContext(catalogSource.slice(0, end) + '\nglobalThis.sdkCatalog = API_REFERENCE;})();', context, {timeout: 1000});
const current = JSON.parse(JSON.stringify(context.sdkCatalog.endpoints)).filter(e => e.host === 'api');
const fixture = JSON.parse(fixtureText);
const shape = endpoint => [endpoint.id, endpoint.method, endpoint.path, endpoint.access];
assert.deepEqual(current.map(shape).sort(), fixture.endpoints.map(shape).sort(), 'Merchant routes or access changed: update SDK methods, fixtures and release notes.');
for (const endpoint of current) {
  const stored = fixture.endpoints.find(e => e.id === endpoint.id);
  assert.deepEqual(endpoint.request.body ?? null, stored.body, `${endpoint.id}: documented request changed`);
  assert.deepEqual(JSON.parse(endpoint.responseExample), stored.response, `${endpoint.id}: documented response changed`);
}
console.log(`PASS: all ${current.length} merchant routes, access levels and public request/response examples match the SDK fixture.`);
