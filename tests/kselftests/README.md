# Kernel Selftests (kselftests)

## Usage

```bash
./scripts/boot/qemu-pseries \
    --cpu POWER10 \
    --cloud-image ubuntu24.04-kselftests-cloudimg-ppc64el.qcow2 \
    --test-name kselftests \
    --test-args "kernel_src=~/workspace/kernels/linux-ppc,target=powerpc/mm" \
    --test-output-dir ./results-tmp
```

## Arguments

### Required
- `kernel_src`: Path to kernel source directory

### Optional
- `target`: Specific test target to run (e.g., `mm`, `powerpc/mm`, `net`, `bpf`)
  - If not specified, runs all tests

## Output

Test results are collected from `~/kselftests-results/` in the VM and packaged as `kselftests-logs.zip` in the specified `--test-output-dir`.