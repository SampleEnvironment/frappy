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
	python3 setup.py build

clean:
	find . -name '*.pyc' -delete
	rm -rf build
	$(MAKE) -C doc clean

install: build
	python3 setup.py install

test:
ifdef T
	python3 $(shell which pytest) -v test -l -k $(T)
else
	python3 $(shell which pytest) -v test -l
endif

test-verbose:
	python3 $(shell which pytest) -v test -s

test-coverage:
	python3 $(shell which pytest) -v test --cov=secop

doc:
	$(MAKE) -C doc html

lint:
	pylint -f colorized -r n --rcfile=.pylintrc secop secop_* test

isort:
	@find test -name '*.py' -print0 | xargs -0 isort -e -m 2 -w 80 -ns __init__.py
	@find secop -name '*.py' -print0 | xargs -0 isort -e -m 2 -w 80 -ns __init__.py
	@find . -wholename './secop_*.py' -print0 | xargs -0 isort -e -m 2 -w 80 -ns __init__.py

release-patch:
	MODE="patch" $(MAKE) release

release-minor:
	MODE="minor" $(MAKE) release

release-major:
	MODE="major" $(MAKE) release

release:
	ssh jenkins.admin.frm2.tum.de -p 29417 build -v -s -p GERRIT_PROJECT=$(shell git config --get remote.origin.url | rev | cut -d '/' -f -2 | rev) -p ARCH=all -p MODE=$(MODE) ReleasePipeline


build-pkg:
	debocker build --image docker.ictrl.frm2.tum.de:5443/mlzbase/buster
