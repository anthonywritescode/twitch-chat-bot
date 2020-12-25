[tox]
envlist = py38,pre-commit
skipsdist = true

[testenv]
deps =
    -rrequirements.txt
    -rrequirements-dev.txt
commands =
    coverage erase
    coverage run -m pytest {posargs:tests}
    coverage report

[testenv:pre-commit]
skip_install = true
deps = pre-commit
commands = pre-commit run --all-files --show-diff-on-failure

[pep8]
ignore = E265,E501,W504
