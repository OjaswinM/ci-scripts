import os
import importlib.util
import logging
import sys

def create_test_instance(test_name, test_args, p):
    """
    Dynamically imports the test class from tests/<test_name>/test.py
    and returns an instance. If test.py is not present return instance
    of GenericTest
    """

    # This is needed to ensure dynamic imports work. Some python importlib magic.
    # Be careful while changing else imports will break and we will get weird
    # errors

    # First ensure project root is correctly set
    PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)

    GenericTest = importlib.import_module("lib.application_tests.base").GenericTest

    # import module dynamically based on the test_name
    module_path = os.path.join(PROJECT_ROOT, "tests", test_name, "test.py")

    if not os.path.exists(module_path):
        logging.error(f"Test specific implementation not found. Running generic test")
        return GenericTest(test_name, p)

    module_name = f"tests.{test_name}.test"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    for obj in module.__dict__.values():
        if not isinstance(obj, type):  # Only process classes
            continue

        # Find a class that inherits from GenericTest
        if isinstance(obj, type) and issubclass(obj, GenericTest) and obj is not GenericTest:
            return obj(test_name, test_args, p)


    logging.error(f"Test specific implementation not found. Running generic test")
    return GenericTest(test_name, test_args, p)
