# SDK maintenance

This repository contains only the public client SDK and inert examples. Never copy
merchant server implementation, private-service files, credentials or wallet data.
SDK semantic versions are independent of merchant releases.

When a public API route, request, response, permission or behavior changes:

1. Update methods, documentation and `tests/fixtures/api-v1.json` together.
2. Extend tests for validation, wire bytes, precision, authentication and retries.
3. Run tests on actual Python 3.10 and current runtimes, not only a parser target.
4. Run the public-contract drift check, type checks and package-content audit.
5. Update `_version.py` and changelog, build wheel/sdist and test both in clean environments.
6. Publish an immutable Git tag and GitHub release, then upload the audited artifacts
   to PyPI. Verify hashes/metadata and a clean install from the default PyPI index.
   Update the README's manual ZIP link. Test the downloaded `src/whollycrypto`
   package without pip or site-packages, both copied beside an application and
   loaded from the intact source layout. Runtime imports must not need distribution metadata.

```bash
node tools/check-api-coverage.mjs /path/to/api-docs.js /path/to/api-examples.js
python -m unittest discover -s tests -t . -v
python -m build
python -m twine check dist/*
```

The drift checker reads only the public API catalog, never the merchant implementation.
Tests use mocks, temporary loopback HTTP/TLS servers and private SQLite. OpenSSL CLI
is needed for generated test certificates. No live invoices or funds are used.

Wheel/sdist selection is allowlisted in pyproject.toml. Credentials and publishing
scripts belong outside the repository. Do not put a PyPI token in Git, a workflow,
a shell command argument or `.pypirc` committed to the repository. Use private
operator storage or appropriately configured trusted publishing.

The optional `ci/github-actions.yml` is not active until a maintainer with workflow
write access places it under `.github/workflows/tests.yml`. It only runs checks;
it has no publishing secret. Run local verification regardless of CI availability.

Changes to JSON canonicalization require special review: invoice idempotency uses
the exact raw body, not semantic JSON equality. Never rewrite a released tag/version.
