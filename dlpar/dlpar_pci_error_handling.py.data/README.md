# DLPAR PCI Hotplug Error Handling Test

## Overview

This test suite validates the error handling improvements in DLPAR (Dynamic Logical Partitioning) PCI hotplug operations for PowerPC systems, specifically testing the patch authored by Wen Xiong that improves error path handling during device addition.

## Patch Information

- **Subject**: [PATCH V2] error path improvement in dlpar add
- **Author**: Wen Xiong <wenxiong@linux.ibm.com>
- **Date**: 2026-02-04 22:38:44
- **Mailing List**: linuxppc-embedded
- **URL**: https://marc.info/?l=linuxppc-embedded&m=177024744319900&w=2

## What the Patch Fixes

The patch addresses a critical issue where device drivers were not being loaded when PCI resource claiming failed during DLPAR hotplug add operations. The improvements include:

1. **Error Propagation**: Functions now return error codes instead of void
2. **Error Detection**: Resource claiming failures are properly detected
3. **Error Reporting**: Appropriate error messages are displayed
4. **Proper Cleanup**: System doesn't leave devices in inconsistent state

### Modified Files
- `arch/powerpc/kernel/pci-common.c`
- `arch/powerpc/kernel/pci-hotplug.c`
- `arch/powerpc/platforms/pseries/pci_dlpar.c`
- `drivers/pci/hotplug/rpadlpar_core.c`

## Test Cases

### Test 1: Normal Add/Remove Operation
Validates basic DLPAR operations work correctly with the patch.

### Test 2: Error Message Verification
Ensures appropriate error messages appear when operations fail.

### Test 3: Return Code Verification
Validates operations return correct exit codes.

### Test 4: Multiple Operations
Tests stability across multiple add/remove cycles.

### Test 5: Memory Leak Check
Validates no memory leaks in error paths.

### Test 6: System Stability (Stress Test)
Validates system remains stable under repeated operations.

## Requirements

### Hardware
- IBM Power System (POWER8, POWER9, or POWER10)
- DLPAR capability enabled
- At least one PCI hotplug slot available

### Software
- Linux kernel with the error handling patch applied
- PowerPC architecture (ppc64/ppc64le)
- Required packages:
  - `powerpc-utils` (provides drmgr, lsslot)
  - `pciutils` (provides lspci)

### Kernel Configuration
```
CONFIG_PPC_PSERIES=y
CONFIG_HOTPLUG_PCI=y
CONFIG_HOTPLUG_PCI_RPA=y
CONFIG_HOTPLUG_PCI_RPA_DLPAR=y
CONFIG_PCI=y
```

## Usage

### Basic Test Run
```bash
# Run with default parameters (auto-detect slot)
avocado run dlpar_pci_error_handling.py

# Run with specific configuration
avocado run dlpar_pci_error_handling.py -m dlpar_pci_error_handling.yaml

# Run specific test case
avocado run dlpar_pci_error_handling.py:DLPARPCIErrorHandling.test_01_normal_add_remove
```

### Configuration Options

Edit `dlpar_pci_error_handling.yaml` to customize:

```yaml
basic_test:
    slot_name: "PHB 391"      # PCI slot name (auto-detect if not specified)
    iterations: 1              # Number of test iterations
    stress_test: False         # Enable stress testing
```

### Finding Available Slots

To find available PCI slots on your system:
```bash
# List all PCI slots
lsslot -c pci

# List PHB (PCI Host Bridge) slots
lsslot -c phb

# List current PCI devices
lspci -tv
```

### Running Stress Tests

For stress testing (50 iterations):
```bash
avocado run dlpar_pci_error_handling.py -m dlpar_pci_error_handling.yaml:stress_test
```

### Serial Execution

Some tests may require serial execution to avoid conflicts:
```bash
avocado run --max-parallel-tasks=1 dlpar_pci_error_handling.py
```

## Expected Results

### Success Indicators
- All test cases pass
- No kernel panics or system crashes
- Proper error messages when operations fail
- Device drivers load only when resource claiming succeeds
- No memory leaks detected
- System remains stable under stress

### Failure Indicators
- System crashes or hangs
- Device drivers loaded despite resource claiming failures
- Missing or incorrect error messages
- Memory or resource leaks
- Kernel panics or BUG messages

## Troubleshooting

### Test Fails to Find Slot
If the test cannot auto-detect a slot:
1. Manually find available slots: `lsslot -c pci`
2. Specify slot in YAML configuration
3. Ensure slot supports hotplug operations

### Permission Denied
DLPAR operations require root privileges:
```bash
sudo avocado run dlpar_pci_error_handling.py
```

### Device Not Responding
If device doesn't respond after add:
1. Check dmesg for errors: `dmesg | tail -50`
2. Verify slot is correct: `lsslot -c pci`
3. Check resource availability: `cat /proc/iomem | grep PCI`

### Enable Debug Logging
For verbose kernel logging:
```bash
# Enable PCI debug
echo 8 > /proc/sys/kernel/printk
echo 'file drivers/pci/* +p' > /sys/kernel/debug/dynamic_debug/control
echo 'file arch/powerpc/kernel/pci* +p' > /sys/kernel/debug/dynamic_debug/control
```

## Interpreting Results

### Test Output
```
JOB ID     : <job_id>
JOB LOG    : /home/user/avocado/job-results/job-<timestamp>/job.log
 (1/6) dlpar_pci_error_handling.py:DLPARPCIErrorHandling.test_01_normal_add_remove: PASS (5.23 s)
 (2/6) dlpar_pci_error_handling.py:DLPARPCIErrorHandling.test_02_error_message_verification: PASS (3.45 s)
 ...
RESULTS    : PASS 6 | ERROR 0 | FAIL 0 | SKIP 0 | WARN 0 | INTERRUPT 0 | CANCEL 0
```

### Log Files
- **Job log**: Contains overall test execution details
- **Test logs**: Individual test case logs with detailed output
- **Debug log**: Kernel messages and system state information

### Checking Kernel Messages
```bash
# View recent kernel messages
dmesg | tail -100

# Search for error messages
dmesg | grep -E "Unable to add hotplug|can't claim|error updating"

# Check for critical errors
dmesg | grep -E "panic|BUG|WARNING"
```

## Integration with CI/CD

### Travis CI Example
```yaml
script:
  - sudo avocado run --max-parallel-tasks=1 dlpar/dlpar_pci_error_handling.py
```

### Jenkins Pipeline Example
```groovy
stage('DLPAR PCI Error Handling Test') {
    steps {
        sh 'sudo avocado run dlpar/dlpar_pci_error_handling.py'
    }
}
```

## Related Tests

- `dlpar_main.py` - General DLPAR operations test
- `io/common/bootlist_test.py` - Boot device testing
- `ras/ras_lsvpd.py` - Hardware diagnostics

## References

- [Patch Discussion](https://marc.info/?l=linuxppc-embedded&m=177024744319900&w=2)
- [PowerPC DLPAR Documentation](https://www.kernel.org/doc/html/latest/powerpc/index.html)
- [PCI Hotplug Documentation](https://www.kernel.org/doc/html/latest/PCI/pci-hotplug.html)
- [Avocado Test Framework](https://avocado-framework.github.io/)

## Contributing

To add new test cases:
1. Add test method to `DLPARPCIErrorHandling` class
2. Follow naming convention: `test_XX_description`
3. Use `self.err_mesg` list for error collection
4. Update this README with test case description

## Support

For issues or questions:
- Check kernel logs: `dmesg`
- Review test logs in avocado results directory
- Consult patch discussion on linuxppc-embedded mailing list
- Verify hardware supports DLPAR operations

## License

This test is part of the avocado-misc-tests suite and follows the same license terms (GPLv2).