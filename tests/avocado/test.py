import logging
from lib.application_tests.base import GenericTest

class AvocadoTest(GenericTest):
    def __init__(self, name, test_args, p):
        # TODO: add comment regarding what the test_args format is
        super().__init__(name, test_args, p)

    def setup(self):
        logging.info(f"Overriding setup() of GenericTest")
        self.p.cmd("make prepare")

    def test(self):
        logging.info(f"Overriding test() of GenericTest")
        self.p.cmd(f"make test {self.test_args}")
        self.p.cmd("cat /root/avocado/job-results/latest/job.log")
