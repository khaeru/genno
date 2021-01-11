Releasing
*********

Before releasing, check:

- https://github.com/khaeru/genno/actions?query=workflow:pytest+branch:master to ensure that the push and scheduled builds are passing.
- https://readthedocs.org/projects/genno/builds/ to ensure that the docs build is passing.

Address any failures before releasing.

1. Edit :file:`doc/whatsnew.rst` to replace "Next release" with the version number and date.
   Make a commit with a message like "Mark vX.Y.Z in whatsnew.rst".

2. Tag the version, e.g.::

    $ git tag v1.2.3b4

3. Test-build and check the source and binary packages::

    $ rm -rf build dist
    $ python setup.py bdist_wheel sdist
    $ twine check dist/*

   Address any warnings or errors that appear.
   If needed, make a new commit and go back to step (2).

4. Upload the packages to the TEST instance of PyPI::

    $ twine upload -r testpypi dist/*

5. Check at https://test.pypi.org/project/genno/ that:

   - The package can be downloaded, installed and run.
   - The README is rendered correctly.
   - Links to the documentation go to the correct version.

   If not, modify the code and go back to step (2).

6. Upload to PyPI::

    $ twine upload dist/*

7. Edit :file:`doc/whatsnew.rst` to add a new heading for the next release.
   Make a commit with a message like "Reset whatsnew.rst to development state".

8. Push the commits and tag to GitHub::

    $ git push --tags

   Visit https://github.com/khaeru/genno/releases and mark the new release using the pushed tag.
