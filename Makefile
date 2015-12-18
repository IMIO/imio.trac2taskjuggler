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

.PHONY: generate_tj
generate_tj:
	if ! test -f bin/generate_tj;then make buildout;fi
	if ! test -d project;then mkdir -p project;fi
	bin/generate_tj 2> output/generation_errors.html;

.PHONY: report
report:
	if ! test -d project;then make generate_tj;fi
	bin/report

.PHONY: cleanall
cleanall:
	rm -fr lib bin/buildout develop-eggs downloads eggs parts .installed.cfg
