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
- [ ] After the release change is merged, create the exact planned version tag
      and verify PyPI, installation and the runnable example on Linux, macOS,
      and Windows, the hosted documentation, and the benchmark smoke/reference
      result.
- [ ] Confirm the release workflow published the expected package to PyPI.
- [ ] Confirm the documentation workflow deployed the matching Sphinx site.
- [ ] After package publication is approved and complete, create and publish the
      matching GitHub Release at the exact tag. Use concise notes from the
      matching `CHANGELOG.md` section, then confirm it is public, not a draft or
      prerelease, and points to the expected tag and merge commit.

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

## GitHub Release Follow-up

After the release change is merged, and only after explicit human approval has
been given for the tag and package publication, the maintainer completes the
follow-up in this order:

1. Create the exact version tag on the merge commit.
2. Wait for the protected `pypi` environment approval and tag-triggered package
   publication to complete.
3. Prepare concise release notes from the matching `CHANGELOG.md` section.
4. Create the release from that tag with
   `gh release create <tag> --verify-tag --title "isobands <tag>" --notes-file <notes-file>`.
5. Verify it with
   `gh release view <tag> --json tagName,isDraft,isPrerelease,targetCommitish`.
   The release must be public, neither a draft nor prerelease, and its tag must
   resolve to the expected merge commit.

The workflow in `.github/workflows/continuous-deployment.yaml` publishes to
PyPI but does not create a GitHub Release. Agents may draft the notes and
verification commands, but must not run the tag, publication, or release
commands without explicit human approval.

## PyPI Trusted Publishing

The tag-triggered release job publishes with GitHub's OpenID Connect token. It
does not use a long-lived PyPI API token and does not create a GitHub Release.

The alpha publication verified this setup. For a release:

1. Keep the repository's `pypi` environment protected.
2. Require approval on the environment if publication should pause for a final
   maintainer review.
3. Publish through the existing Trusted Publisher; do not add a long-lived
   PyPI API token.
4. After package publication is approved and complete, follow the GitHub Release
   Follow-up above to create and verify the matching release.
