# Contributing

Thanks for improving `isobands`. Please open an issue for substantial changes
and keep pull requests focused. The package is alpha software, so document
user-facing behavior changes in `docs/`, `README.md`, and the `Unreleased`
section of `CHANGELOG.md`.

## Required GDAL installation

Development uses GDAL **3.12.2**, including matching system development
headers. The PyPI GDAL package is source-only and compiles against the system
library; pip alone is not enough.

Install GDAL 3.12.2 with your Unix/macOS package manager or from source, then
verify:

```sh
gdal-config --version  # must print 3.12.2
```

Windows contributors should use conda-forge for the native dependency:

```sh
conda install -c conda-forge gdal=3.12.2
```

## Development workflow

Install all locked dependency groups:

```sh
make install
```

Run the fast, non-mutating checks:

```sh
make check
```

Run the complete local suite, including tests, package build, and strict docs:

```sh
make verify
```

Useful focused checks include:

```sh
make install-docs
make docs-check
make package-check PACKAGE=isobands
```

Use `UV_NO_ENV_FILE=1` when invoking `uv` directly, as the Makefile does.
Keep tests serial while the suite is small; use `make test-serial` for
debugging shared state.

## Documentation

Sphinx source is in `docs/` and uses MyST Markdown. Add public behavior to the
usage and limitations pages, and keep the autosummary API page current. Build
strictly with `make docs-check`; do not add production hosting URLs while
hosting is deferred.

## Releases

See [RELEASING.md](RELEASING.md) for the release checklist. Trusted Publishing
and remote environment configuration are maintainer-owned setup tasks. Do not
create tags, releases, deployments, or package publications without explicit
maintainer approval.
