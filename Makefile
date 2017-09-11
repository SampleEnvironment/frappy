.PHONY: all doc clean test

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
	$(MAKE) -C doc/srcdoc html

demo:
	@bin/secop-server -q demo &
	@bin/secop-server -q test &
	@bin/secop-server -q cryo &
	@bin/secop-gui localhost:10767 localhost:10768 localhost:10769
	@ps aux|grep [s]ecop-server|awk '{print $$2}'|xargs kill

test:
	#@pytest -v --lf -l --tb=auto --setup-plan test/
	@pytest -v --lf -l --tb=long --setup-show test/
