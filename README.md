# django-stateless-mcp

![PyPI version](https://img.shields.io/pypi/v/django-stateless-mcp.svg)

Stateless Model Context Protocol (MCP) server for Django, built on the 2026-07-28 spec.

* [GitHub](https://github.com/Streamlined-Analytics/django-stateless-mcp/) | [PyPI](https://pypi.org/project/django-stateless-mcp/) | [Documentation](https://Streamlined-Analytics.github.io/django-stateless-mcp/)
* Created by [Ben Atkinson](https://streamlinedanalytics.co.uk) | GitHub [@BenA-SA](https://github.com/BenA-SA) | PyPI [@streamlined-analytics](https://pypi.org/user/streamlined-analytics/)
* MIT License

## Features

* TODO

## Documentation

Documentation is built with [Zensical](https://zensical.org/) and deployed to GitHub Pages.

* **Live site:** https://Streamlined-Analytics.github.io/django-stateless-mcp/
* **Preview locally:** `just docs-serve` (serves at http://localhost:8000)
* **Build:** `just docs-build`

API documentation is auto-generated from docstrings using [mkdocstrings](https://mkdocstrings.github.io/).

Docs deploy automatically on push to `main` via GitHub Actions. To enable this, go to your repo's Settings > Pages and set the source to **GitHub Actions**.

## Development

To set up for local development:

```bash
# Clone your fork
git clone git@github.com:your_username/django-stateless-mcp.git
cd django-stateless-mcp

# Install in editable mode with live updates
uv tool install --editable .
```

This installs the CLI globally but with live updates - any changes you make to the source code are immediately available when you run `django_stateless_mcp`.

Run tests:

```bash
uv run pytest
```

Run quality checks (format, lint, type check, test):

```bash
just qa
```

## Author

django-stateless-mcp was created in 2026 by Ben Atkinson.

Built with [Cookiecutter](https://github.com/cookiecutter/cookiecutter) and the [audreyfeldroy/cookiecutter-pypackage](https://github.com/audreyfeldroy/cookiecutter-pypackage) project template.
