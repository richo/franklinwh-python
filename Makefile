# Debug pretty printer
print-%: ; @echo $*=$($*)

build:
	rm -rf dist
	python3 -m build

release:
	python3 -m twine upload dist/*

.PHONY: build release
