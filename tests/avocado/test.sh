#!/bin/bash

source venv/bin/activate
cd avocado-misc-tests-master
avocado run fs/xfstests.py -m fs/xfstests.py.data/ext4/ci.yaml
