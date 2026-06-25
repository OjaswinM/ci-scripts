import logging

class GenericTest:
    """
    The GenericTest class is responsible for downloading, compiling and running
    the tests. It assumes that everythin in ci-scripts/<test_name>/* has
    already been copied into the VM and we have cd'd into the test dir.

    The generic implementation here assumes that the test directory has a
    Makefile which does most of the work. Refer tests/avocado/Makefile for
    reference implementation. Hence all we do here is to invoke make. Incase
    a test wants their logic they need to define a child class in
    tests/<test_name>/test.py. Refer tests/avocado/test.py for reference.
    """
    def __init__(self, name, test_args, p):
        self.name = name
        self.p = p
        self.test_args = test_args  # Dict of raw args from --test-args
        self.parsed_args = {}  # Dict of validated/parsed args

    def parse_common_args(self):
        """
        Populate parsed_args with the raw --test-args values.
        """
        self.parsed_args = self.test_args.copy()

    def parse_args(self):
        """
        Override this method to validate and parse test-specific arguments.

        Should populate self.parsed_args with validated values.
        Raise ValueError if required args are missing or invalid.

        Example:
            def parse_args(self):
                self.parse_common_args()

                # Check required args
                if 'config' not in self.parsed_args:
                    raise ValueError("Missing required argument: config")

                # Validate and store
                self.parsed_args['config'] = self.parsed_args['config']

                # Optional args with defaults
                self.parsed_args['timeout'] = int(self.parsed_args.get('timeout', 3600))

        Returns:
            None
        """
        self.parse_common_args()

    def preboot(self, qconf):
        """
        Called before VM boot to allow test to modify qemu configuration.
        Tests can override this to add custom mounts, modify cmdline, etc.

        Args:
            qconf: QemuConfig object that can be modified

        Returns:
            None
        """
        pass

    def setup(self):
        self.p.cmd("make prepare")

    def test(self, *args, **kwargs):
        """
        Test callback is called in the VM to run the test.
        """
        self.p.cmd(f"make test {self.test_args}")

    def collect_logs(self, *args, **kwargs):
        """
        Collect logs once the test run is done
        """
        logging.info(f"Log collection not implemented for {self.name}")
        pass
