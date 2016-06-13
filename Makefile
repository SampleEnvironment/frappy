.PHONY: all doc clean

all: clean doc

clean:
	@echo "cleaning pyc files"
	@find . -name '*.pyc' -delete
	@echo "cleaning html tree"
	@rm -rf html
	@mkdir html

doc: doc/*.md
	@echo "Generating html tree"
	@bin/make_doc.py

