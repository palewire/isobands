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
- [ ] Confirm the planned version's section in `CHANGELOG.md` is complete.
- [x] Confirm the protected `pypi` GitHub environment and matching PyPI Trusted
      Publisher are configured for `.github/workflows/continuous-deployment.yaml`.
- [ ] Obtain explicit human approval before any release tag or publication.
- [ ] Tag the planned version and verify PyPI, installation and the runnable
      example on Linux, macOS, and Windows, the hosted documentation, and the
      benchmark smoke/reference result.
- [ ] Confirm the release workflow published the expected package to PyPI.
- [ ] Confirm the documentation workflow deployed the matching Sphinx site.
- [ ] After PyPI and release checks pass, create and publish the matching GitHub
      Release at the exact tag. Use concise or generated release notes, then
      confirm it is public, not a draft or prerelease, and links to that tag.

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
does not use a long-lived PyPI API token and does not create a GitHub Release.

The alpha publication verified this setup. For a release:

1. Keep the repository's `pypi` environment protected.
2. Require approval on the environment if publication should pause for a final
   maintainer review.
3. Publish through the existing Trusted Publisher; do not add a long-lived
   PyPI API token.
4. After confirming PyPI and release checks pass, create and publish the
   matching GitHub Release at the exact tag. Add concise notes or use generated
   notes, then verify the release is public, neither draft nor prerelease, and
   links to the intended tag.
