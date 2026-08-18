# Releasing

This project follows [Semantic Versioning](https://semver.org/) and [Keep a
Changelog](https://keepachangelog.com/en/1.1.0/). Package versions come from
Git tags through `setuptools-scm`; do not edit a version file.

## Release Checklist

- [ ] Replace all template metadata and configure the package layout described
      in `AGENTS.md`.
- [ ] Document public package behavior in the Sphinx source under `docs/`.
- [ ] Run `make docs-check`.
- [ ] Run `make verify`.
- [ ] Run `make package-check PACKAGE=<import-name>`.
- [ ] Run `make coverage PACKAGE=<import-name>`.
- [ ] Confirm the planned stable `0.1.0` section in `CHANGELOG.md` is complete
      before cutting the release candidate. The RC and stable release must be
      able to tag the same commit.
- [x] Confirm the protected `pypi` GitHub environment and matching PyPI Trusted
      Publisher are configured for `.github/workflows/continuous-deployment.yaml`.
- [ ] Obtain explicit human approval before any release tag or publication.
- [ ] Tag `0.1.0rc1` and verify PyPI, installation and the runnable example on
      Linux, macOS, and Windows, the hosted documentation, and the benchmark
      smoke/reference result.
- [ ] If any release-candidate change is needed, make it, verify it, and tag
      `0.1.0rc2`; every changed RC requires the next RC number.
- [ ] Once the RC is accepted, tag `0.1.0` on the unchanged RC commit and
      confirm the release workflow published the expected package to PyPI.
- [ ] Confirm the documentation workflow deployed the matching Sphinx site.

## Exact RC-to-stable flow

The stable section and all release documentation must be prepared before the
RC. After explicit maintainer approval:

1. Tag `0.1.0rc1` from the verified commit.
2. Verify PyPI installation and the example on Linux, macOS, and Windows;
   verify the hosted docs and the benchmark smoke/reference result.
3. If anything changes, tag `0.1.0rc2` (and continue with `rc3` if needed) and
   repeat all verification.
4. When an RC is accepted without further changes, tag `0.1.0` on that exact
   unchanged commit.

The `Development Status :: 5 - Production/Stable` classifier is intentionally
present before the RC so package metadata is stable during this flow.

## Documentation Deployment

Package documentation lives in this repository under `docs/`. The
`.github/workflows/docs.yaml` workflow builds the Sphinx site on every push and
pull request.

Before publishing documentation, protect the `docs-production` environment and
configure an AWS OIDC role with `DOCS_AWS_ROLE_ARN` and `DOCS_AWS_REGION`. Then
set the `DOCS_DEPLOY_ENABLED` repository variable to `true`. Keep deployment in
the same workflow so the published site always comes from the reviewed Sphinx
source in this repository.

## Agent Boundaries

Agents may update release documentation and run the checklist's validation
commands. They must not create tags, GitHub releases, documentation
deployments, or package publications without explicit human approval.

## PyPI Trusted Publishing

The tag-triggered release job publishes with GitHub's OpenID Connect token. It
does not use a long-lived PyPI API token.

The alpha publication verified this setup. For the stable release:

1. Keep the repository's `pypi` environment protected.
2. Require approval on the environment if publication should pause for a final
   maintainer review.
3. Publish through the existing Trusted Publisher; do not add a long-lived
   PyPI API token.
