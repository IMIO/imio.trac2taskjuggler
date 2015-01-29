#!/bin/bash

cd /srv/projects/imio.trac2taskjuggler
# 2 empty echo needed to avoid 500 response
echo
echo
echo "Content-type:  text/plain\n";
make generate_tj
make report
