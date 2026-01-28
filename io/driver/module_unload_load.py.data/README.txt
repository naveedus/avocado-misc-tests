Module Unload/Load Test
========================

This test validates kernel module unloading and reloading functionality for I/O drivers.

CONFIGURATION FILE:
-------------------

The test uses a "config" file (not YAML) that lists kernel modules to test.
Each line in the config file should contain one module name.

Example config file content:
```
bnx2x
mlx5_core
nvme
lpfc
qla2xxx
```

PARAMETERS:
-----------

The test reads module names from the "config" file in the .data directory.
No YAML parameters are required.

TEST CASES:
-----------

1. Reads list of modules from config file
2. For each module:
   - Checks if module is currently loaded
   - Attempts to unload the module
   - Verifies module is unloaded
   - Reloads the module
   - Verifies module is loaded again
   - Checks for any errors in dmesg
3. Validates module functionality after reload

RUNNING TESTS:
--------------

# Run module unload/load test
avocado run avocado-misc-tests/io/driver/module_unload_load.py

# The test automatically reads from module_unload_load.py.data/config

PREREQUISITES:
--------------

1. Root/sudo privileges required
2. Modules must not be in use by active devices
3. Module dependencies must be resolvable
4. System must support module unloading (not built-in)

NOTES:
------

- Test skips modules that are built-in (cannot be unloaded)
- Modules with active users will fail to unload
- Test checks dmesg for errors after each operation
- Some modules may have dependencies that prevent unloading
- Network modules may cause temporary connectivity loss

CONFIGURATION:
--------------

Edit the "config" file to add or remove modules to test.
One module name per line, no special formatting required.

TROUBLESHOOTING:
----------------

- If module fails to unload: Check for active users with `lsmod`
- If module fails to reload: Check dmesg for error messages
- Some modules require specific hardware to function
- Ensure no critical services depend on the module
- Network modules: Ensure alternative connectivity exists

WARNINGS:
---------

- Unloading storage drivers may cause data loss
- Unloading network drivers will interrupt connectivity
- Test with caution on production systems
- Some modules cannot be safely unloaded while system is running

# Assisted with AI tools
