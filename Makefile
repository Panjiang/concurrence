CWD=$(shell pwd)
ifndef PYTHON
    export PYTHON=python2.6
endif
ifndef DESTDIR
    export DESTDIR=$(CWD)/debian/tmp
endif
export PYTHONPATH=/usr/share/pyshared:$(DESTDIR)/usr/lib/$(PYTHON)

.PHONY: test install doc

build:
	$(PYTHON) setup.py build

ext:
	$(PYTHON) setup.py build_ext --inplace
	
egg:
	$(PYTHON) setup.py bdist_egg
				
install: build
	mkdir -p $(DESTDIR)/usr/lib/$(PYTHON)
	$(PYTHON) setup.py install --prefix=$(DESTDIR)/usr --install-purelib=$(DESTDIR)/usr/lib/$(PYTHON) --install-platlib=$(DESTDIR)/usr/lib/$(PYTHON) --install-layout=deb --root=/

sdist:
	$(PYTHON) setup.py sdist

doc:
	rm -rf doc/html
	cd doc/src; make html
	cp -a doc/src/_build/html doc/html
 
clean:
	-find . -name *.pyc -exec rm -rf {} \;
	-find . -name *.so -exec rm -rf {} \;
	-find . -name *.dep -exec rm -rf {} \;
	-find . -name *~ -exec rm -rf {} \;
	-find . -name *.egg-info -exec rm -rf {} \;
	rm -rf setuptools*.egg
	rm -rf doc/src/_build
	rm -rf build dist
	rm -rf lib/concurrence/database/mysql/concurrence.database.mysql._mysql.c
	rm -rf lib/concurrence/concurrence._event.c
	rm -rf lib/concurrence/io/concurrence.io._io.c
	rm -rf lib/concurrence/http/concurrence.http._http.c
	rm -rf test/htmlcov

dist_clean: clean
	find . -name .svn -exec rm -rf {} \;

test: install
	cd test; make test

test-test: install
	$(PYTHON) test/testtest.py

test-core: install
	$(PYTHON) test/testcore.py

test-memcache: install
	$(PYTHON) test/testmemcache.py

coverage:
	cd test; coverage erase
	cd test; PYTHON="coverage run -a " make test
	cd test; rm -rf htmlcov
	cd test; coverage html -d htmlcov
	firefox test/htmlcov/index.html& 
