# Publishing to PyPI

screen-watch is installable from GitHub today:

```bash
pip install "git+https://github.com/JadissEL/screen-watch.git@v0.2.9"
```

## When you are ready for PyPI

1. Create a PyPI project `screen-watch` (or reserve the name).
2. Preferred: **Trusted Publishing** (OIDC) from GitHub Actions — no long-lived token in the repo.
3. Or set repository secret `PYPI_API_TOKEN` — the `release` workflow publishes on `v*` tags (`continue-on-error` if the secret is missing).
4. Tag a release: `git tag -a vX.Y.Z -m "…" && git push origin vX.Y.Z`

Build locally:

```bash
python -m pip install build
python -m build
```
