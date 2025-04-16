#!/bin/bash

source venv/bin/activate
cd avocado-misc-tests-master

avocado run fs/xfstests.py -m fs/xfstests.py.data/${1:-ext4}/${2:-ci.yaml}
