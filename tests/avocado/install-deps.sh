#!/bin/bash

set -euo pipefail

. /etc/os-release

sudo=""
if [[ $(id -u) != 0 ]]; then
    sudo="sudo"
fi

if [[ "$ID" == "fedora" ]]; then
        set -x
        $sudo dnf -y install python3 python3-pip python3-venv unzip
elif [[ "${ID_LIKE:-$ID}" == "debian" ]]; then
	export DEBIAN_FRONTEND=noninteractive
        set -x
        $sudo apt -y install python3 python3-pip python3-venv unzip
else
    echo "Unsupported distro!" >&2
    exit 1
fi

# avocado setup
python3 -m venv venv
source venv/bin/activate
pip3 install avocado-framework
pip3 install avocado-framework-plugin-varianter-yaml-to-mux

#avocado misc test download
name=avocado-misc-tests
tarball=$name.zip
#url=https://github.com/avocado-framework-tests/avocado-misc-tests/archive/refs/heads/master.zip
url=https://github.com/OjaswinM/avocado-misc-tests/archive/refs/heads/master.zip

curl -L -o $tarball.tmp $url
mv $tarball.tmp $tarball
unzip $tarball
cd $name-master
