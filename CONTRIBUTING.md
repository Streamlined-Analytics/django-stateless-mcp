# Contributing

Contributions are welcome, and they are greatly appreciated! Every little bit helps, and credit will always be given.

## Bugs and feature ideas

Report bugs and propose features at https://github.com/Streamlined-Analytics/django-stateless-mcp/issues.
For bugs, include your Python and Django versions and detailed steps to reproduce; anything tagged "help wanted" is open to whoever wants to implement it.

## Documentation

To preview the docs locally:

```sh
just docs-serve
```

This starts a local server at http://localhost:8000 with live reload. Edit files in `docs/` or add docstrings to your code (the API reference page is auto-generated).

## Get Started!

Ready to contribute? Start with [ARCHITECTURE.md](ARCHITECTURE.md) — the map of how the package works, the three invariants every change must preserve, and the traps that have already bitten. Then here's how to set up django-stateless-mcp for local development.

1. Fork the django-stateless-mcp repo on GitHub.
2. Clone your fork locally:

   ```sh
   git clone git@github.com:your_name_here/django-stateless-mcp.git
   ```

3. Install your local copy with uv:

   ```sh
   cd django-stateless-mcp/
   uv sync
   ```

4. Create a branch for local development:

   ```sh
   git checkout -b name-of-your-bugfix-or-feature
   ```

   Now you can make your changes locally.

5. When you're done making changes, check that your changes pass linting and the tests:

   ```sh
   just qa
   ```

   Or run the tests alone:

   ```sh
   just test
   ```

6. Commit your changes and push your branch to GitHub:

   ```sh
   git add .
   git commit -m "Your detailed description of your changes."
   git push origin name-of-your-bugfix-or-feature
   ```

7. Submit a pull request through the GitHub website.

## Pull Request Guidelines

Before you submit a pull request, check that it meets these guidelines:

1. The pull request should include tests.
2. If the pull request adds functionality, the docs should be updated. Put your new functionality into a function with a docstring, and add the feature to the "What it provides" list in README.md.
3. The pull request should work on every supported Python and Django combination (see "Supported versions" in README.md). Tests run in GitHub Actions on every pull request to the main branch; make sure they pass for the whole matrix.

## Tips

To run a subset of tests:

```sh
uv run pytest tests/
```

Coverage is gated at 100%, so a new line needs a test or a `# pragma: no cover`
carrying its reason. Measure it with:

```sh
just coverage
```

That runs the suite on every supported interpreter *and* the multi-worker fleet
tests, which are skipped by a plain `pytest` run and are the only cover for
`tests/test_multiworker.py`.

## Releasing a New Version

1. **Bump the version** and **write the changelog:**
   ```bash
   uv version <version>        # or: uv version --bump minor
   ```
   Then write `CHANGELOG/<version>.md`. See previous entries for the format.
2. **Commit:**
   ```bash
   git add pyproject.toml uv.lock CHANGELOG/
   git commit -m "Release <version>"
   ```
3. **Release:**
   ```bash
   just release
   ```
   This creates an annotated `v*` tag, pushes it to GitHub, and creates a
   GitHub Release with the changelog contents as release notes. The tag
   push triggers `.github/workflows/publish.yml`, which builds the package,
   generates SLSA provenance attestations, and publishes to PyPI via
   trusted publishing.

## Code of Conduct

Please note that this project is released with a [Contributor Code of Conduct](CODE_OF_CONDUCT.md). By participating in this project you agree to abide by its terms.
