# Include ixmp test fixtures, e.g. pre-populated Scenario objects
# TODO remove this dependency
# NB genno must follow ixmp, since pytest prefers fixtures etc. from later in the list
pytest_plugins = ("ixmp.testing", "genno.testing")
