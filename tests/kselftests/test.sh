#!/bin/bash

set -e

TARGET=${1:-all}
KERNEL_SRC=${2}

echo "Running kselftests for target: $TARGET"

# Create results directory
mkdir -p ~/kselftests-results

# Validate kernel source path
if [ -z "$KERNEL_SRC" ]; then
    echo "Error: KERNEL_SRC not provided"
    echo "Usage: $0 <target> <kernel_src_path>"
    exit 1
fi

if [ ! -d "$KERNEL_SRC/tools/testing/selftests" ]; then
    echo "Error: Invalid kernel source path: $KERNEL_SRC"
    echo "tools/testing/selftests directory not found"
    exit 1
fi

echo "Using kernel source at: $KERNEL_SRC"

# Navigate to selftests directory
cd "$KERNEL_SRC/tools/testing/selftests"

# Run the tests
if [ "$TARGET" = "all" ]; then
    echo "Running all selftests..."
    make run_tests 2>&1 | tee ~/kselftests-results/run.log
else
    echo "Running selftests for: $TARGET"

    # Handle nested paths like powerpc/syscalls
    TARGET_DIR="$KERNEL_SRC/tools/testing/selftests/$TARGET"
    if [ ! -d "$TARGET_DIR" ]; then
        echo "Error: Target directory not found: $TARGET_DIR"
        exit 1
    fi

    cd "$TARGET_DIR" || exit 1
    echo "Running tests in: $(pwd)"
    make run_tests 2>&1 | tee ~/kselftests-results/${TARGET//\//_}.log
fi

echo "Kselftests completed. Results saved to ~/kselftests-results/"
