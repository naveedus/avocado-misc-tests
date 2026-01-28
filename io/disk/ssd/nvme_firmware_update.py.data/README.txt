NVMe Firmware Update Test Suite
=================================

This test suite provides comprehensive firmware update tests with pre/post validation.

PARAMETERS:
-----------

"device": The NVMe controller name. Required parameter.
  Accepts values in the following formats:
  1. NQN (Name Space Qualifier Name): nqn.1994-11.com.vendor:nvme:modela:2.5-inch:SERIALNUM
  2. Subsystem: nvme-subsysX
  3. Controller: nvmeX
  
  Example: device: nvme0

"firmware_url": URL to download firmware binary. Required parameter.
  Supports direct binary files and archives
  Supported formats: .bin, .fw, .rom, .zip, .tar.gz, .tgz, .tar.bz2
  
  Examples:
    - Direct binary: https://example.com/firmware/nvme_fw_v1.2.3.bin
    - Archive: https://example.com/firmware/nvme_fw_v1.2.3.zip
    - Local file: file:///path/to/firmware.bin

"force_update": Force update even if same firmware version (default: true)
  Set to true to allow updating with same version firmware
  Useful for testing firmware update process without version change
  
  Example: force_update: true

"slot": Firmware slot to use (default: 0 for next available)
  Values: 0 (auto-select next available), 1-7 (specific slot)
  Some controllers support multiple firmware slots
  
  Example: slot: 0

"action": Firmware commit action (default: 1)
  Values:
    0: Downloaded image replaces the image indicated by the slot field
    1: Downloaded image replaces the image indicated by the slot field and is activated
    2: The image indicated by the slot field is activated (no download)
    3: Downloaded image replaces the Boot Partition image
  
  Most common: action 1 (download and activate)
  
  Example: action: 1

TEST CASES:
-----------

1. test_firmware_update_standard()
   - Downloads firmware from URL
   - Reads pre-update firmware version
   - Performs firmware download to controller
   - Commits firmware to specified slot
   - Resets controller to activate firmware
   - Validates post-update firmware version
   - Verifies controller and namespaces are accessible

2. test_firmware_update_force_same_version()
   - Specifically tests force update with same firmware version
   - Validates that force_update parameter works correctly
   - Ensures firmware can be re-applied even if version matches
   - Verifies controller remains stable after force update
   - Confirms firmware revision stays same (expected behavior)

3. test_firmware_update_with_slot_selection()
   - Tests firmware update to specific slot (slot 1)
   - Validates slot-based firmware management
   - Verifies active slot changes after update
   - Confirms firmware is loaded in correct slot

VALIDATION:
-----------

Pre-Update Validation:
- Reads current firmware revision from nvme id-ctrl
- Captures firmware slot information from nvme fw-log
- Records active firmware slot
- Logs all slot versions

Post-Update Validation:
- Waits for controller stabilization (5 seconds)
- Reads new firmware revision
- Compares pre/post firmware versions
- Verifies controller accessibility (nvme id-ctrl)
- Checks all namespaces are still accessible
- Validates device nodes exist
- Confirms active firmware slot (if applicable)

Force Update Validation:
- For same-version updates, verifies revision stays same
- Ensures controller remains functional
- Validates no data loss or corruption

FIRMWARE UPDATE PROCESS:
------------------------

1. Download Phase:
   - Fetch firmware from URL
   - Extract if archive format
   - Verify file exists and is readable
   - Log firmware file size

2. Controller Download:
   - Use nvme fw-download command
   - Transfer firmware to controller memory
   - Verify download success

3. Commit Phase:
   - Use nvme fw-commit command
   - Specify slot and action
   - Commit firmware to selected slot

4. Activation:
   - Reset controller via sysfs or nvme reset
   - Wait for controller to come back online (up to 60 seconds)
   - Verify controller accessibility

5. Validation:
   - Compare firmware versions
   - Check controller functionality
   - Verify namespace accessibility

RUNNING TESTS:
--------------

# Run all firmware update tests
avocado run avocado-misc-tests/io/disk/ssd/nvme_firmware_update.py -m avocado-misc-tests/io/disk/ssd/nvme_firmware_update.py.data/nvme_firmware_update.yaml

# Run specific test
avocado run avocado-misc-tests/io/disk/ssd/nvme_firmware_update.py:NVMeFirmwareUpdate.test_firmware_update_standard -m <yaml_file>
avocado run avocado-misc-tests/io/disk/ssd/nvme_firmware_update.py:NVMeFirmwareUpdate.test_firmware_update_force_same_version -m <yaml_file>
avocado run avocado-misc-tests/io/disk/ssd/nvme_firmware_update.py:NVMeFirmwareUpdate.test_firmware_update_with_slot_selection -m <yaml_file>

PREREQUISITES:
--------------

1. nvme-cli must be installed
2. NVMe controller must support firmware updates
3. Valid firmware binary URL must be provided
4. Root/sudo privileges required for firmware operations
5. Controller must not be in use during update
6. Backup all data before firmware update
7. Ensure firmware is compatible with controller model

FIRMWARE COMPATIBILITY:
-----------------------

CRITICAL: Always verify firmware compatibility before updating!

- Check controller model and vendor
- Verify firmware is for correct model
- Review firmware release notes
- Test on non-production system first
- Have rollback plan ready

To check controller model:
  nvme id-ctrl /dev/nvmeX | grep -E "mn|sn|fr"

SAFETY WARNINGS:
----------------

⚠️  FIRMWARE UPDATE IS A CRITICAL OPERATION ⚠️

- Incorrect firmware can brick the device
- Always backup data before updating
- Verify firmware compatibility with controller
- Do not interrupt update process
- Ensure stable power supply
- Test on non-production systems first
- Have recovery plan ready
- Some updates may require multiple reboots
- Controller may be temporarily unavailable during update

TROUBLESHOOTING:
----------------

If firmware update fails:
1. Check nvme-cli version (should be recent)
2. Verify firmware file integrity
3. Check controller supports firmware updates:
   nvme id-ctrl /dev/nvmeX | grep frmw
4. Review controller logs:
   nvme error-log /dev/nvmeX
5. Try different slot or action value
6. Ensure no I/O operations during update
7. Check system logs: dmesg | grep nvme

If controller doesn't come back online:
1. Wait longer (some updates take time)
2. Try manual reset: echo 1 > /sys/class/nvme/nvmeX/reset_controller
3. Reboot system
4. Check BIOS/UEFI settings
5. Contact vendor support if device is bricked

NOTES:
------

- Firmware download is cached for 7 days
- Controller reset may take up to 60 seconds
- Some controllers require system reboot for activation
- Firmware slots allow multiple firmware versions
- Active slot can be changed without re-downloading
- Import errors in IDE can be ignored - avocado framework must be installed
- Test logs include detailed firmware information
- tearDown logs final firmware state for verification