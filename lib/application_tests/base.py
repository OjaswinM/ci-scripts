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
    def __init__(self, name, p):
        self.name = name
        self.p = p

    def setup(self):
        self.p.cmd("make prepare")

    def test(self, *args, **kwargs):
        """
        Test callback is called in the VM to run the test.
        """
        self.p.cmd("make test")

    def collect_logs(self, *args, **kwargs):
        """
        Collect logs once the test run is done
        """
        logging.info(f"Log collection not implemented for {self.name}")
        pass
