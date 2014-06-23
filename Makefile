#!/usr/bin/make
#
all: run

.PHONY: bootstrap
bootstrap:
	virtualenv-2.7 .
	./bin/python bootstrap.py

.PHONY: buildout
buildout:
	if ! test -f bin/buildout;then make bootstrap;fi
	bin/buildout -v;

.PHONY: trac
trac:
	if ! test -f bin/generate_tj;then make buildout;fi
	if ! test -d project;then mkdir -p project/output;fi
	bin/generate_tj;

.PHONY: tj
tj:
	if ! test -d project;then make trac;fi
	cp custom.css project/output/css/
	tj3  -o project/output project/trac.tjp

.PHONY: cleanall
cleanall:
	rm -fr lib bin/buildout develop-eggs downloads eggs parts .installed.cfg
