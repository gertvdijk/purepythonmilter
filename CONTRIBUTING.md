<!--
SPDX-FileCopyrightText: 2023 Gert van Dijk <github@gertvandijk.nl>

SPDX-License-Identifier: CC0-1.0
-->

# Contributing

Your contributions, in any form, are very much welcome! 🙏

When contributing to this repository with a proposed change to the code, please first
discuss the change you wish to make in an [issue][github-new-issue] (for bugs or
features), create a [discussion][github-new-discussion] post in case anything is
unclear, write me an email (`github@gertvandijk.nl`) or any other method with
the owners of this repository before making a change.

## Getting started with development

1. Get a copy of the repository and change your current directory in the project root.

1. Create a clean Python 3.10.x virtual environment and activate it.
   Suggested way is to install [direnv][direnv-home] together with [Pyenv][pyenv-github]
   and use the project-supplied `.envrc` (`direnv allow`).

1. Make sure the base Python packages such as `pip`, `setuptools` and `setuptools-scm`
   are up-to-date *inside this virtualenv*.

   ```console
   $ pip install --upgrade pip setuptools setuptools-scm[toml]
   ```

1. This should list zero outdated packages at this point:

   ```console
   $ pip list --outdated
   ```

1. Install the project with development and examples dependencies with this virtualenv
   active.
   E.g.:

    ```console
    $ pip install -e .[development,examples]
    ```

1. Verify that all tests pass by running `pytest`.

    ```console
    $ pytest
    [...]
    ==== 211 passed in 1.09s ====
    ```

1. Verify that you can run the `run-all-linters` script.

   This requires [hadolint][hadolint-github] and [shellcheck][shellcheck-home] to be
   installed on the system.

    ```console
    $ ./run-all-linters
    [...]
    Everything looks OK! 🎉
    ```

1. Now you're ready to make your changes!

### Suggested IDE: VS Code

The repository ships with helpers for use with
[Microsoft Visual Studio Code][ms-vscode-home].
It suggests extensions, performs strict mypy type checking on the fly, visual indicators
for code style (e.g. 88-chars ruler), provides a task with 'problemMatcher' to run the
`run-all-linters` script and more.

In order for them to work correctly, please
[select the Python interpreter][ms-vscode-select-python] of the virtualenv you created,
e.g. `.direnv/python-3.10.9/bin/python`.
The linters and type checker will then be run inside this environment created with
specific versions specified rather than relying on whatever is available system-wide.

ℹ️ If you like, enable automatic on-save formatting with project-provided settings using
the user-level setting `editor.formatOnSave`.
It will run `black` for you whenever hitting Save on a file.

## Pull Request Process

ℹ️ The aim for this workflow is to end up with a clean git history which should be
helpful for anyone else in the future (e.g. using git-blame, git-log).

1. Fork the repository to your own GitHub account.
1. Push the change(s) to your local fork, preferably to brach with a self-descriptive
   name.
   Please use a clean git commit history with descriptive commit messages and refer to
   relevant issues or discussions.
   In case your work was done in multiple iterations, use amending and/or an interactive
   rebase to craft a set of contained commits.
1. Ensure that your fork's branch is based off with latest upstream `develop` branch.
   If not, fetch latest changes and *rebase* it.
1. Run the `run-all-linters` script to ensure all code adheres to the code style, strict
   typing requirements and licensing headers.
1. Run `pytest` to ensure your code changes do not break current tests (adjust if
   necessary) and your newly introduced lines are all covered by new/adjusted tests
   (compare coverage output).
1. All ready?!
   Create a pull request targeting the `develop` branch.
   Write a title that consicely describes the main aim of the changes in the request.
   Consider to tick the *"Allow edits by maintainers"* checkbox (see below).
1. Please allow the maintainer to take the time to review and test the code.
   In case code changes are requested, please amend the commit(s) affected and update
   the commit message(s) if necessary.

ℹ️ If you're uncomfortable to rebase/amend or unsure about commit message wording or even
adjusting test cases, please indicate that the maintainer is allowed to edit your pull
request when creating the pull request.
Then in the pull request description kindly request the maintainer to apply the work on
that and consider to mark the pull request as [draft][github-draft-pr-howto].

Notes:

- Ideally, every single commit should be reversible and have a single responsibility.
  Preparatory work leading up to an actual change should happen in separate commit(s) to
  aid reviewing and having a useful git history.
  Example of a well-crafted set of commits:

  `HEAD   Implement feature X`<br/>
  — the aim of the pull request

  `HEAD^  Refactor module Y to allow for subclassing ClassZ`<br/>
  — improvement, but preparatory change

  `HEAD^^ Add tests for current logic in module Y`<br/>
  — not a functional change in itself, but purely preparatory to assert a before-change
  state is tested for.

- Please adhere to the following style in commit messages:

  - Use present tense.
  - Avoid captain obvious-only commit messages like *"Delete file x"* or
    *"Update file y"*, because, well, anyone can see precisely that when looking at the
    diff.
  - Add the reason for the change (if not obvious).
    To have a *why* later looking at the changes is very useful, e.g. when creating
    release notes or even at review time understanding for the need to include the
    change.

- Please avoid merge commits in your pull request; use rebase instead.
  Merge commits are harder to revert and to cherry-pick.
- Pull requests should apply cleanly on the latest upstream `develop` branch.
  Preferably, your branch should be 'fast-forwardable' in git-speak.
- The maintainer is free to cherry-pick, amend and push your work in a pull request's
  commits directly to any branch, effectively bypassing GitHub's pull request 'merge'
  button.
  Attributions will be preserved by either the commit's author field or a
  `Co-authored-by` footer in the commits.

  This also enables to move forward with dependent commits in a pull request still
  pending discussion on the adoption of that actual feature or bug fix approach.
  E.g. the two commits at the bottom (`Update code style ...`, `Refactor module Y ...`)
  could be merged for everyone to profit from already and reducing the size of the pull
  request pending review as well.

- At the expense of the clean git history policy GPG/SSH signatures on commits by
  contributors could be lost as a result of the amendments by non-authors.
  If you wish to maintain your digitally verifiable signature, please take the time to
  submit your pull request in a state it can be *fast-forward*ed and rebase whenever
  the target branch is updated (which may be frequent).

[github-new-issue]: https://github.com/gertvdijk/purepythonmilter/issues/new/choose
[github-new-discussion]: https://github.com/gertvdijk/purepythonmilter/discussions/new
[direnv-home]: https://direnv.net/
[pyenv-github]: https://github.com/pyenv/pyenv
[hadolint-github]: https://github.com/hadolint/hadolint
[shellcheck-home]: https://www.shellcheck.net/
[ms-vscode-home]: https://code.visualstudio.com/
[ms-vscode-select-python]: https://code.visualstudio.com/docs/python/environments#_work-with-python-interpreters
[github-draft-pr-howto]: https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/about-pull-requests#draft-pull-requests
