# Debug pretty printer
print-%: ; @echo $*=$($*)

build:
	python3 -m build

release:
	python3 -m twine upload dist/*

.PHONY: build release
