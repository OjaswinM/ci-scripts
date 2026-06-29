import logging
from lib.application_tests.base import GenericTest

class AvocadoTest(GenericTest):

    SUPPORTED_FS = ['ext4', 'xfs', 'btrfs']

    def __init__(self, name, test_args, p):
        super().__init__(name, test_args, p)

    def parse_args(self):
        """
        Parse and validate avocado test arguments.

        Required args:
        - fs_type: Filesystem type (ext2, ext4, xfs, btrfs)
        - config: Path to YAML config file

        """
        if 'fs_type' not in self.test_args:
            raise ValueError("Missing required argument: fs_type")
        if 'config' not in self.test_args:
            raise ValueError("Missing required argument: config")

        fs_type = self.test_args['fs_type']
        if fs_type not in self.SUPPORTED_FS:
            raise ValueError(
                f"Invalid fs_type '{fs_type}'. "
                f"Must be one of: {', '.join(self.SUPPORTED_FS)}"
            )

        self.parsed_args['fs_type'] = fs_type
        self.parsed_args['config'] = self.test_args['config']

    def setup(self):
        logging.info(f"Setting up avocado test")
        self.p.cmd("make prepare")

    def test(self):
        logging.info(f"Running avocado test")

        fs = self.parsed_args['fs_type']
        config = self.parsed_args['config']

        self.p.cmd(f'make test FS={fs} CONFIG="{config}"')

    def collect_logs(self, output_dir):
        """
        output_dir is the dir in the VM where shared host dir is mounted.
        """
        if not output_dir:
            logging.warn(f"Output dir empty. Logs will not be stored")

        self.p.cmd(f"cd ~/avocado/job-results/latest/.")
        self.p.cmd(f"zip -r {output_dir}/avocado-logs.zip ./*")
