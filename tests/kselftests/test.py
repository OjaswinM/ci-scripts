import logging
import os
from lib.application_tests.base import GenericTest

class KselftestsTest(GenericTest):
    def __init__(self, name, test_args, p):
        super().__init__(name, test_args, p)
        self.kernel_src_mount = None

    def parse_args(self):
        """
        Parse and validate kselftests arguments.

        Required args:
        - kernel_src: Path to kernel source directory

        Optional args:
        - target: Specific test target to run (default: powerpc/syscalls)
        """
        self.parse_common_args()

        if 'kernel_src' not in self.parsed_args:
            raise ValueError("Missing required argument: kernel_src (path to kernel source)")

        kernel_src_path = os.path.expanduser(self.parsed_args['kernel_src'])

        if not os.path.isdir(kernel_src_path):
            raise ValueError(f"Kernel source path not found: {kernel_src_path}")

        self.parsed_args['kernel_src'] = kernel_src_path
        self.parsed_args['target'] = self.parsed_args.get('target', 'powerpc/syscalls')

    def preboot(self, qconf):
        """
        Mount kernel source directory before VM boot.
        """
        kernel_src_path = self.parsed_args['kernel_src']

        # Add kernel source to host mounts
        mount_index = len(qconf.host_mounts)
        qconf.host_mounts.append(kernel_src_path)
        self.kernel_src_mount = f"/mnt/host{mount_index}"

        logging.info(f"Kernel source will be mounted at {self.kernel_src_mount}")

    def setup(self):
        logging.info(f"Setting up kselftests")
        self.p.cmd("make prepare")

    def test(self):
        logging.info(f"Running kselftests")

        target = self.parsed_args['target']
        logging.info(f"Running kselftests target: {target}")

        self.p.cmd(f"make test TARGET={target} KERNEL_SRC={self.kernel_src_mount}")

    def collect_logs(self, output_dir):
        """
        output_dir is the dir in the VM where shared host dir is mounted.
        """
        if not output_dir:
            logging.warn(f"Output dir empty. Logs will not be stored")
            return

        self.p.cmd(f"cd ~/kselftests-results/.")
        self.p.cmd(f"zip -r {output_dir}/kselftests-logs.zip ./*")
