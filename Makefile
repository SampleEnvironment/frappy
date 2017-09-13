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
	python $(shell which pytest) -v test

test-verbose:
	python $(shell which pytest) -v test -s

test-coverage:
	python $(shell which pytest) -v test --cov=secop

doc:
	$(MAKE) -C doc html

lint:
	pylint -j $(shell nproc) -f colorized -r n --rcfile=pylintrc secop secop_* test

.PHONY: doc clean test test-verbose test-coverage demo lint
