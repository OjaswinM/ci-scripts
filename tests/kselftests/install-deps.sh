#!/bin/bash

set -e

echo "Installing kselftests dependencies..."

# Detect OS
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
else
    echo "Cannot detect OS"
    exit 1
fi

# Install dependencies based on OS
if [ "$OS" = "ubuntu" ] || [ "$OS" = "debian" ]; then
    apt-get update
    apt-get install -y \
        build-essential \
        git \
        libelf-dev \
        libcap-dev \
        libcap-ng-dev \
        libnuma-dev \
        libfuse-dev \
        libmnl-dev \
        pkg-config \
        rsync \
        zip
elif [ "$OS" = "fedora" ] || [ "$OS" = "rhel" ] || [ "$OS" = "centos" ]; then
    dnf install -y \
        gcc \
        make \
        git \
        elfutils-libelf-devel \
        libcap-devel \
        libcap-ng-devel \
        numactl-devel \
        fuse-devel \
        libmnl-devel \
        pkgconfig \
        rsync \
        zip
else
    echo "Unsupported OS: $OS"
    exit 1
fi

echo "Dependencies installed successfully"
exit 0
