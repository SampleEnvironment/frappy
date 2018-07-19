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

.PHONY: doc clean test test-verbose test-coverage demo lint

all: # no build necessary

install:
	find * -maxdepth 0 -name '*' -not -path 'debian' \
		-not -name 'Makefile' -exec cp -rv {} $(DESTDIR) \;
	find .* -maxdepth 0 -name '*' -not -path '.git' \
		-not -path '.' -not -path '..' -exec cp -rv {} $(DESTDIR) \;

rename: OLDNAME = $(shell grep 'Source: boxes-' debian/control | cut -d '-' -f 2)
rename:
ifndef NEWNAME
	@echo "No image name given.\nGive via NEWNAME environment variable."
else
	@echo "Rename from $(OLDNAME) to $(NEWNAME) ..."
	@find debian -type f -exec sed -i -e "s/$(OLDNAME)/$(NEWNAME)/g" {} \;
endif

first-commit:
	git add .
	git commit -m 'Add basic image files.'

init-changelog: FIRST_COMMIT = $(shell git rev-list --reverse HEAD | head -1)
init-changelog:
	gbp dch --new-version=0.0.0 --debian-tag='v%(version)s' --ignore-branch --since=$(FIRST_COMMIT)
	git add debian/changelog
	git commit -m '[deb] Init changelog.'

create-first-tag:
	git tag -a -m "Release v0.0.0" v0.0.0
	git push origin HEAD:refs/heads/master
	git push --tags


init: first-commit init-changelog create-first-tag

release-patch:
	MODE="patch" $(MAKE) release

release-minor:
	MODE="minor" $(MAKE) release

release-major:
	MODE="major" $(MAKE) release

release:
	ssh jenkinsng.admin.frm2 -p 29417 build -v -s -p GERRIT_PROJECT=$(shell git config --get remote.origin.url | rev | cut -d '/' -f -3 | rev) -p ARCH=all -p MODE=$(MODE) ReleasePipeline

build:
	ssh jenkinsng.admin.frm2 -p 29417 build -v -s -p NAME=$(shell git config --get remote.origin.url | rev | cut -d '/' -f 1 | rev) DebianBuildImage

.PHONY: rename init release release-patch release-minor release-major build

