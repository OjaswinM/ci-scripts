# Avocado Test

## Usage

```bash
./scripts/boot/qemu-pseries \
    --cpu POWER9 \
    --cloud-image ubuntu24.04-cloudimg-ppc64el.qcow2 \
    --test-name avocado \
    --test-args "fs_type=ext4,config=4k.yaml" \
    --test-output-dir ./results-tmp
```

## Arguments

### Required
- `fs_type`: Filesystem type - must be one of: `ext2`, `ext4`, `xfs`, `btrfs`
- `config`: Path to avocado YAML config file.Note that the avocado test will look for <fs_type>/<config> [here](https://github.com/avocado-framework-tests/avocado-misc-tests/tree/master/fs/xfstests.py.data) to find the yaml file

## Output

Test logs are packaged as `avocado-logs.zip` in the specified `--test-output-dir`.
