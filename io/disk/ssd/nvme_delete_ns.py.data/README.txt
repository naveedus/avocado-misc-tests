NVMe Namespace Deletion Test Suite
===================================

This test suite provides comprehensive namespace deletion tests with validation.

PARAMETERS:
-----------

"device": The NVMe controller name. Required parameter.
  Accepts values in the following formats:
  1. NQN (Name Space Qualifier Name): nqn.1994-11.com.vendor:nvme:modela:2.5-inch:SERIALNUM
  2. Subsystem: nvme-subsysX
  3. Controller: nvmeX
  
  Example: device: nvme0

"namespace_id": Specific namespace ID to delete (used by test_delete_single_namespace)
  Optional - test creates its own namespaces if not specified
  
  Example: namespace_id: 1

"restore_full_capacity": Whether to restore single full capacity namespace after test (default: true)
  If true, tearDown will delete all namespaces and create one full capacity namespace
  Recommended to keep as true to leave controller in clean state
  
  Example: restore_full_capacity: true

TEST CASES:
-----------

1. test_delete_single_namespace()
   - Creates 3 test namespaces
   - Deletes the middle namespace
   - Validates deleted namespace is removed from:
     * nvme list command output
     * /dev/ device nodes
     * /sys/class/nvme/ sysfs entries
   - Verifies other namespaces remain intact

2. test_delete_all_namespaces()
   - Creates 5 test namespaces
   - Deletes all namespaces using nvme.delete_all_ns()
   - Validates all namespaces are removed
   - Verifies no namespace entries remain in system

3. test_delete_multiple_specific_namespaces()
   - Creates 6 test namespaces
   - Deletes alternate namespaces (1st, 3rd, 5th)
   - Validates only specified namespaces are deleted
   - Verifies remaining namespaces (2nd, 4th, 6th) still exist

4. test_delete_and_recreate_namespace()
   - Creates a single namespace
   - Records namespace properties
   - Deletes the namespace
   - Validates deletion
   - Recreates namespace with full capacity
   - Verifies new namespace is accessible

VALIDATION:
-----------

Each test performs comprehensive validation:
- Checks nvme list command no longer shows deleted namespaces
- Verifies /dev/nvmeXnY device nodes are removed
- Confirms /sys/class/nvme/nvmeX/nvmeXnY sysfs entries are gone
- Validates namespace count matches expected value
- For partial deletions, verifies remaining namespaces are intact

RUNNING TESTS:
--------------

# Run all deletion tests
avocado run avocado-misc-tests/io/disk/ssd/nvme_delete_ns.py -m avocado-misc-tests/io/disk/ssd/nvme_delete_ns.py.data/nvme_delete_ns.yaml

# Run specific test
avocado run avocado-misc-tests/io/disk/ssd/nvme_delete_ns.py:NVMeDeleteNamespace.test_delete_single_namespace -m <yaml_file>
avocado run avocado-misc-tests/io/disk/ssd/nvme_delete_ns.py:NVMeDeleteNamespace.test_delete_all_namespaces -m <yaml_file>
avocado run avocado-misc-tests/io/disk/ssd/nvme_delete_ns.py:NVMeDeleteNamespace.test_delete_multiple_specific_namespaces -m <yaml_file>
avocado run avocado-misc-tests/io/disk/ssd/nvme_delete_ns.py:NVMeDeleteNamespace.test_delete_and_recreate_namespace -m <yaml_file>

PREREQUISITES:
--------------

1. nvme-cli must be installed
2. NVMe controller must support namespace management
3. Root/sudo privileges required for namespace operations
4. Controller must not be in use (no mounted filesystems on namespaces)
5. Tests create their own namespaces, so existing namespaces will be deleted

TEST WORKFLOW:
--------------

Each test follows this pattern:
1. Delete any existing namespaces (cleanup)
2. Create test namespaces with known configuration
3. Perform deletion operation
4. Rescan controller to update system state
5. Validate deletion through multiple checks:
   - nvme list command
   - Device node existence
   - Sysfs entry existence
   - Namespace list from nvme utility
6. Verify expected namespaces remain (for partial deletion tests)

NOTES:
------

- Tests automatically create and cleanup namespaces
- Controller rescan is performed after namespace operations
- 2-second delays included for namespace detection/removal
- tearDown restores controller to single full capacity namespace by default
- Import errors in IDE can be ignored - avocado framework must be installed to run
- Tests are destructive - existing namespaces will be deleted

SAFETY:
-------

- Always backup data before running these tests
- Tests will delete ALL existing namespaces during setup
- Use restore_full_capacity: true to leave controller in usable state
- Do not run on production systems with active data