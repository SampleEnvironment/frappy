.PHONY: release release-patch release-minor release-major
.PHONY: all doc clean test test-verbose test-coverage demo lint build install

all: clean doc

demo:
	@bin/secop-server -q demo &
	@bin/secop-server -q test &
	@bin/secop-server -q cryo &
	@bin/secop-gui localhost:10767 localhost:10768 localhost:10769
	@ps aux|grep [s]ecop-server|awk '{print $$2}'|xargs kill

build:
	python setup.py build

clean:
	find . -name '*.pyc' -delete
	rm -rf build
	$(MAKE) -C doc clean

install: build
	python setup.py install

test:
ifdef T
	python $(shell which pytest) -v test -l -k $(T)
else
	python $(shell which pytest) -v test -l
endif

test-verbose:
	python $(shell which pytest) -v test -s

test-coverage:
	python $(shell which pytest) -v test --cov=secop

doc:
	$(MAKE) -C doc html

lint:
	pylint -j $(shell nproc) -f colorized -r n --rcfile=.pylintrc secop secop_* test

release-patch:
	MODE="patch" $(MAKE) release

release-minor:
	MODE="minor" $(MAKE) release

release-major:
	MODE="major" $(MAKE) release

release:
	ssh jenkinsng.admin.frm2 -p 29417 build -v -s -p GERRIT_PROJECT=$(shell git config --get remote.origin.url | rev | cut -d '/' -f -3 | rev) -p ARCH=all -p MODE=$(MODE) ReleasePipeline


