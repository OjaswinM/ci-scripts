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
        #self.p.cmd("cat /root/avocado/job-results/job.log")

    def collect_logs(self, output_dir):
        """
        output_dir is the dir in the VM where shared host dir is mounted.
        """
        if not output_dir:
            logging.warn(f"Output dir empty. Logs will not be stored")

        self.p.cmd(f"cd ~/avocado/job-results/latest/.")
        self.p.cmd(f"zip -r {output_dir}/avocado-logs.zip ./*")
