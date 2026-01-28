NVMe Namespace Creation Test Suite
====================================

This test suite provides comprehensive namespace creation tests with validation.

PARAMETERS:
-----------

"device": The NVMe controller name. Required parameter.
  Accepts values in the following formats:
  1. NQN (Name Space Qualifier Name): nqn.1994-11.com.vendor:nvme:modela:2.5-inch:SERIALNUM
  2. Subsystem: nvme-subsysX
  3. Controller: nvmeX
  
  Example: device: nvme0

"namespace_count": Number of namespaces to create for equal-sized test (default: 4)
  Used by test_create_equal_size_namespaces()
  Must not exceed controller's maximum namespace count
  
  Example: namespace_count: 4

"restore_full_capacity": Whether to restore single full capacity namespace after test (default: false)
  If true, tearDown will delete all namespaces and create one full capacity namespace
  
  Example: restore_full_capacity: false

TEST CASES:
-----------

1. test_create_full_capacity_namespace()
   - Creates a single namespace using 100% of controller capacity
   - Validates namespace appears in:
     * nvme list command output
     * /dev/ device nodes
     * /sys/class/nvme/ sysfs entries
   - Verifies namespace capacity matches controller capacity

2. test_create_max_namespaces()
   - Creates maximum number of namespaces supported by controller
   - Each namespace gets equal capacity (60% of total divided equally)
   - Validates all namespaces are created and accessible
   - Verifies each namespace can be queried with nvme id-ns

3. test_create_equal_size_namespaces()
   - Creates specified number of equal-sized namespaces (from namespace_count parameter)
   - Validates all namespaces created successfully
   - Verifies all namespaces have approximately equal size (within 10% variance)
   - Checks namespace accessibility via device nodes and nvme commands

VALIDATION:
-----------

Each test performs comprehensive validation:
- Checks nvme list command shows all created namespaces
- Verifies /dev/nvmeXnY device nodes exist
- Confirms /sys/class/nvme/nvmeX/nvmeXnY sysfs entries present
- Tests namespace accessibility with nvme id-ns command
- Validates namespace count matches expected value

RUNNING TESTS:
--------------

# Run all creation tests
avocado run avocado-misc-tests/io/disk/ssd/nvme_create_ns.py -m avocado-misc-tests/io/disk/ssd/nvme_create_ns.py.data/nvme_create_ns.yaml

# Run specific test
avocado run avocado-misc-tests/io/disk/ssd/nvme_create_ns.py:NVMeCreateNamespace.test_create_full_capacity_namespace -m <yaml_file>
avocado run avocado-misc-tests/io/disk/ssd/nvme_create_ns.py:NVMeCreateNamespace.test_create_max_namespaces -m <yaml_file>
avocado run avocado-misc-tests/io/disk/ssd/nvme_create_ns.py:NVMeCreateNamespace.test_create_equal_size_namespaces -m <yaml_file>

PREREQUISITES:
--------------

1. nvme-cli must be installed
2. NVMe controller must support namespace management
3. Controller should not have existing namespaces (tests will delete them)
4. Root/sudo privileges required for some operations
5. Controller must not be in use (no mounted filesystems on namespaces)

NOTES:
------

- Tests automatically delete existing namespaces before creating new ones
- Controller rescan is performed after namespace operations
- Each test includes 2-second delays for namespace detection
- Import errors in IDE can be ignored - avocado framework must be installed to run