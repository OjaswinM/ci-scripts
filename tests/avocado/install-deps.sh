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
pip3 install --upgrade pip wheel
pip3 install "setuptools<72" # Use <72 to ensure it is compatible with avocado
pip3 install avocado-framework
pip3 install avocado-framework-plugin-varianter-yaml-to-mux

#avocado misc test download
name=avocado-misc-tests
tarball=$name.zip
#url=https://github.com/avocado-framework-tests/avocado-misc-tests/archive/refs/heads/master.zip
url=https://github.com/OjaswinM/avocado-misc-tests/archive/refs/heads/master.zip

# Retry download up to 3 times with timeout
max_retries=3
retry_count=0
while [ $retry_count -lt $max_retries ]; do
    if curl -L --connect-timeout 30 --max-time 300 -o $tarball.tmp $url; then
        # Validate download is a valid zip file (check for PK signature)
        if file $tarball.tmp | grep -q "Zip archive"; then
            mv $tarball.tmp $tarball
            break
        else
            echo "Downloaded file is not a valid zip archive, retrying..." >&2
            rm -f $tarball.tmp
        fi
    fi
    retry_count=$((retry_count + 1))
    if [ $retry_count -lt $max_retries ]; then
        echo "Download failed, retrying ($retry_count/$max_retries)..." >&2
        sleep 5
    else
        echo "Failed to download after $max_retries attempts" >&2
        exit 1
    fi
done

unzip $tarball
cd $name-master

# Write success marker
echo "SUCCESS" > /tmp/avocado-prepare-success
