# Contributing

Thanks for improving `isobands`. Please open an issue for substantial changes
and keep pull requests focused. Document user-facing behavior changes in
`docs/`, `README.md`, and the `Unreleased` section of `CHANGELOG.md`.

## Required GDAL installation

Development uses GDAL **3.12.2**, including matching system development
headers. The PyPI GDAL package is source-only and compiles against the system
library; pip alone is not enough.

Install GDAL 3.12.2 with your Linux/macOS package manager or from source, then
verify:

```sh
gdal-config --version  # must print 3.12.2
```

Windows contributors should use a conda-forge environment for the native
dependency, matching the Windows CI smoke job:

```sh
conda create -n isobands python=3.13
conda activate isobands
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

## Documentation and examples

Sphinx source is in `docs/` and uses MyST Markdown. Add public behavior to the
usage and limitations pages, and keep the autosummary API page current. Build
strictly with `make docs-check`, then run `make linkcheck`. The hosted URL is
kept as plain text in source until deployment makes it available.

Run the real-world example without writing tracked files:

```sh
python examples/air_temperature.py
```

The compact fixture is generated from the pinned NOAA/NCEP source only when
explicitly requested:

```sh
UV_NO_ENV_FILE=1 uv run --no-sync python \
  tests/generate_air_temperature_fixture.py --download
```

Review the checksum and metadata in
`examples/data/air_temperature_time0.source.json` after regeneration.

## Benchmarks

Run the checked-in fixture smoke benchmark before changing benchmark code:

```sh
make benchmark-smoke
```

Run the full comparison when timing behavior changes:

```sh
make benchmark
```

The full run interpolates the pinned native 25x53 source slice to its
configured benchmark grid outside timing, validates both workflows, and writes
reports under `benchmarks/results/`. Benchmark results are informational; do
not add performance thresholds or claim the contour algorithm itself is faster.

## Releases

See [RELEASING.md](RELEASING.md) for the release checklist. Trusted Publishing
and remote environment configuration are maintainer-owned setup tasks. Do not
create tags, releases, deployments, or package publications without explicit
maintainer approval.
