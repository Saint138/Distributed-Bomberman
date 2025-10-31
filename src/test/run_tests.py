"""
Script to run all unit tests for the Bomberman project.
"""
import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def run_all_tests():
    """Execute all test cases in the 'test' directory"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    test_dir = os.path.join(os.path.dirname(__file__), 'test')
    if not os.path.exists(test_dir):
        test_dir = os.path.dirname(__file__)
    discovered_tests = loader.discover(test_dir, pattern='test*.py')
    suite.addTests(discovered_tests)
    runner = unittest.TextTestRunner(verbosity=2)
    print("=" * 70)
    print("EXECUTION OF BOMBERMAN TESTS")
    print("=" * 70)
    print()
    result = runner.run(suite)
    print()
    print("=" * 70)
    print("RIEPILOGO TEST")
    print("=" * 70)
    print(f"Executed tests: {result.testsRun}")
    print(f"Successful: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    if result.failures:
        print("\nTest failures:")
        for test, traceback in result.failures:
            print(f"  - {test}")
    if result.errors:
        print("\nTest with errors:")
        for test, traceback in result.errors:
            print(f"  - {test}")
    return 0 if result.wasSuccessful() else 1

def run_specific_test_module(module_name):
    """
    Execute a specific test module by name
    Args:
        module_name (str): The name of the test module to run
    Returns:
        int: 0 if all tests passed, 1 otherwise
    """
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    try:
        test_module = loader.loadTestsFromName(module_name)
        suite.addTests(test_module)
        runner = unittest.TextTestRunner(verbosity=2)
        print(f"Test execution for: {module_name}")
        print("-" * 50)
        result = runner.run(suite)
        return 0 if result.wasSuccessful() else 1

    except Exception as e:
        print(f"Error in loading: {module_name}: {e}")
        return 1


def run_coverage_report():
    """
    Execute tests with coverage measurement
    Returns:
        int: 0 if all tests passed, 1 otherwise
    """
    try:
        import coverage
        cov = coverage.Coverage()
        cov.start()
        run_all_tests()
        cov.stop()
        cov.save()
        print("\n" + "=" * 70)
        print("COVERAGE REPORT")
        print("=" * 70)
        cov.report(show_missing=True)
        print("\nReport generation HTML in: htmlcov/index.html")
        cov.html_report(directory='htmlcov')

    except ImportError:
        return 1
    return 0

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Run Bomberman unit tests.')
    parser.add_argument('--module', '-m', type=str, help='Execute a specific test module by name')
    parser.add_argument('--coverage', '-c', action='store_true', help='Execute tests with coverage measurement')
    args = parser.parse_args()
    exit_code = 0
    if args.coverage:
        exit_code = run_coverage_report()
    elif args.module:
        exit_code = run_specific_test_module(args.module)
    else:
        exit_code = run_all_tests()
    sys.exit(exit_code)