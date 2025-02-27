import logging
from lib.application_tests.base import GenericTest

class AvocadoTest(GenericTest):
    def __init__(self, name, p):
        super().__init__(name, p)

    def setup(self):
        logging.info(f"Overriding setup() of GenericTest")
        self.p.cmd("make prepare")

    def test(self):
        logging.info(f"Overriding test() of GenericTest")
        self.p.cmd("make test")
        self.p.cmd("cat /root/avocado/job-results/latest/job.log")
