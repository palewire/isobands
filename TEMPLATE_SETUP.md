# Alpha setup checklist

This checklist records the repository setup completed for the `isobands`
alpha. Items that require maintainer or remote-service configuration remain
explicitly deferred.

## Package

- [x] Replace placeholder metadata in `pyproject.toml`.
- [x] Create `src/isobands/` and enable setuptools package discovery.
- [x] Set coverage source and ty include path.
- [x] Add `py.typed` for the typed public API.
- [x] Confirm no Click entry point is needed.

## Documentation

- [x] Replace the distribution placeholder in `docs/conf.py`.
- [x] Add an autosummary-based API reference for the public function.
- [x] Document installation, API semantics, CRS, nodata, coordinates,
      thresholds, limitations, and the in-memory example.
- [ ] Configure production Sphinx hosting (deferred).
- [ ] Protect the remote `docs-production` environment and configure its AWS
      OIDC role and `DOCS_DEPLOY_ENABLED=true` (deferred).

## Continuous integration and repository settings

- [x] Enable unconditional wheel installation, import, and coverage verification
      for `isobands` in CI.
- [ ] Configure required checks and review rules for the default branch
      (deferred; requires repository access).

## Release

- [x] Document the alpha release plumbing and Trusted Publishing workflow.
- [ ] Register the PyPI environment and publisher for Trusted Publishing
      (deferred; remote configuration is not complete).
- [x] Review the release checklist and move alpha changes into the
      `0.1.0a1` dated release section.
- [ ] Create and publish the first release (deferred; requires explicit
      maintainer approval).
