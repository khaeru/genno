Releasing
*********

Before releasing, check:

- https://github.com/khaeru/genno/actions/workflows/pytest.yaml?query=branch:main to ensure that the push and scheduled builds are passing.
- https://readthedocs.org/projects/genno/builds/ to ensure that the docs build is passing.

Address any failures before releasing.

1. Create a new branch::

    $ git checkout -b release/X.Y.Z.

2. Edit :file:`doc/whatsnew.rst`.
   Comment the heading "Next release", then insert another heading below it, at the same level, with the version number and date.
   Commit this change with a message like::

    $ git commit -m "Mark vX.Y.Z in doc/whatsnew".

3. Tag the release candidate version, i.e. with a ``rcN`` suffix, and push::

    $ git tag vX.Y.Zrc1
    $ git push --tags origin release/X.Y.Z

4. Open a PR with the title “Release vX.Y.Z” using this branch.
   Check:

   - at https://github.com/khaeru/genno/actions/workflows/publish.yaml that the workflow completes: the package builds successfully and is published to TestPyPI.
   - at https://test.pypi.org/project/genno/ that:

      - The package can be downloaded, installed and run.
      - The README is rendered correctly.

   - that all other continuous integration (CI) workflows pass.

   Address any warnings or errors that appear.
   If needed, make (an) additional commit(s) and go back to step (3), incrementing the rc number.

5. Merge the PR using the ‘rebase and merge’ method.

6. (optional) Switch back to the ``main`` branch; tag the release itself (*without* an rc number), and push::

    $ git checkout main
    $ git pull --fast-forward
    $ git tag vX.Y.Z
    $ git push --tags origin main

   This step (but *not* step (3)) can also be performed directly on GitHub; see (7), next.

7. Visit https://github.com/khaeru/genno/releases and mark the new release: either using the pushed tag from (6), or by creating the tag and release simultaneously.

8. Check at https://github.com/khaeru/genno/actions/workflows/publish.yaml and https://pypi.org/project/genno/ that the distributions are published.
