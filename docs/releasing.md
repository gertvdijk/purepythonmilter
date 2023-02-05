<!--
SPDX-FileCopyrightText: 2023 Gert van Dijk <github@gertvandijk.nl>

SPDX-License-Identifier: CC0-1.0
-->

# Releasing Purepythonmilter

1. Create an annotated and signed git tag.
   Make sure the commit lives on a branch available in the GitHub repository and the
   working tree is clean.

   ```console
   $ git status  # Should show 'nothing to commit, working tree clean'
   $ git branch --all --contains HEAD
   $ git tag --annotate --sign --message="<Release description>" <tagname>
   ```

1. Build a Python source distribution file and a wheel using `build`.

   ```console
   $ rm -rf dist/
   $ python -m build
   $ ls -l dist/
   ```

1. Upload to PyPI testing and verify the release.

   *The magic username `__token__` is a literal that enables the use of an HTTP API key
   which is needed for accounts with 2FA enabled.*

   When asked for the password, enter the HTTPS API token key with the account on
   test-PyPI for uploading packages to the project.

   ```console
   $ twine check --strict dist/*
   $ TWINE_USERNAME=__token__ twine upload --sign --repository testpypi dist/*
   ```

1. Upload to regular PyPI.

   ```console
   $ TWINE_USERNAME=__token__ twine upload --sign dist/*
   ```

1. Push the git tag to GitHub.

   ```console
   $ git push <remotename> refs/tags/<tagname>:refs/tags/<tagname>
   ```
