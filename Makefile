# Debug pretty printer
print-%: ; @echo $*=$($*)

build:
	rm -rf dist
	python3 -m build

release:
	python3 -m twine upload dist/*

prepare:
	python3 -m pip install -e .[bin,build]

.PHONY: build release prepare
