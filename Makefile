.PHONY: install-test test unit integration build check-dist release-check

install-test:
	python3 -m pip install '.[test]' build twine

test:
	python3 -m pytest -q

unit:
	python3 -m pytest tests/unit -q

integration:
	python3 -m pytest tests/integration -m integration -q

build:
	python3 -m build

check-dist:
	python3 -m twine check dist/*

release-check:
	./scripts/release_check.sh
