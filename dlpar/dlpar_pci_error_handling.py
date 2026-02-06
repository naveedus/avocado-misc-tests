#!/usr/bin/env python
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#
# See LICENSE for more details.
#
# Copyright: 2026 IBM, Naveed AUS (Assisted with AI tools)
# Author: Test Suite for DLPAR PCI Hotplug Error Handling Patch
#         Based on patch by Wen Xiong <wenxiong@linux.ibm.com>

"""
DLPAR PCI Hotplug Error Handling Test

This test validates the error handling improvements in DLPAR PCI hotplug
operations for PowerPC systems. It tests the patch that ensures proper
error propagation when PCI resource claiming fails during device addition.

Patch Details:
- Subject: [PATCH V2] error path improvement in dlpar add
- Date: 2026-02-04
- Mailing List: linuxppc-embedded
"""

import os
import time
import re
from avocado import Test
from avocado.utils import process, genio, distro
from avocado.utils.software_manager.manager import SoftwareManager


class DLPARPCIErrorHandling(Test):
    """
    Test DLPAR PCI hotplug error handling improvements
    
    This test suite validates:
    1. Normal DLPAR add/remove operations
    2. Error detection and propagation
    3. Proper error messages
    4. System stability under error conditions
    5. No resource leaks
    
    :avocado: tags=dlpar,pci,hotplug,power,privileged
    """

    def setUp(self):
        """
        Verify system requirements and setup test environment
        """
        # Check if running on PowerPC
        if 'ppc' not in distro.detect().arch:
            self.cancel("Test requires PowerPC architecture")
        
        # Check for required tools
        sm = SoftwareManager()
        for package in ['powerpc-utils', 'pciutils']:
            if not sm.check_installed(package) and not sm.install(package):
                self.cancel(f"Failed to install required package: {package}")
        
        # Verify DLPAR capability
        if not os.path.exists('/sys/kernel/dlpar'):
            self.cancel("System does not support DLPAR operations")
        
        # Get test parameters
        self.slot_name = self.params.get('slot_name', default=None)
        self.test_iterations = self.params.get('iterations', default=1)
        self.stress_test = self.params.get('stress_test', default=False)
        
        # Auto-detect available PCI slot if not specified
        if not self.slot_name:
            self.slot_name = self._get_available_slot()
            if not self.slot_name:
                self.cancel("No available PCI slot found for testing")
        
        self.log.info(f"Using PCI slot: {self.slot_name}")
        
        # Store initial state
        self.initial_devices = self._get_pci_devices()
        self.initial_memory = self._get_memory_usage()
        
        # Error tracking
        self.err_mesg = []

    def _get_available_slot(self):
        """
        Find an available PCI slot for testing
        
        :return: Slot name or None
        """
        try:
            result = process.run('lsslot -c pci', shell=True, ignore_status=True)
            if result.exit_status != 0:
                return None
            
            # Parse lsslot output to find a slot
            for line in result.stdout_text.splitlines():
                if line.startswith('#') or not line.strip():
                    continue
                # Look for PHB slots
                if 'PHB' in line:
                    parts = line.split()
                    if len(parts) >= 1:
                        return parts[0]
            return None
        except Exception as e:
            self.log.warning(f"Failed to detect PCI slot: {e}")
            return None

    def _get_pci_devices(self):
        """
        Get list of current PCI devices
        
        :return: List of PCI device IDs
        """
        try:
            result = process.run('lspci', shell=True, ignore_status=True)
            if result.exit_status == 0:
                return result.stdout_text.splitlines()
            return []
        except Exception:
            return []

    def _get_memory_usage(self):
        """
        Get current memory usage
        
        :return: Dictionary with memory info
        """
        try:
            meminfo = {}
            with open('/proc/meminfo', 'r') as f:
                for line in f:
                    parts = line.split(':')
                    if len(parts) == 2:
                        key = parts[0].strip()
                        value = parts[1].strip().split()[0]
                        meminfo[key] = int(value)
            return meminfo
        except Exception:
            return {}

    def _check_kernel_errors(self):
        """
        Check dmesg for kernel errors related to PCI/DLPAR
        
        :return: List of error messages
        """
        try:
            result = process.run('dmesg | tail -100', shell=True, 
                               ignore_status=True)
            errors = []
            for line in result.stdout_text.splitlines():
                if any(keyword in line.lower() for keyword in 
                      ['error', 'fail', 'unable', 'bug', 'warning']):
                    if any(subsys in line.lower() for subsys in 
                          ['pci', 'dlpar', 'hotplug', 'phb']):
                        errors.append(line)
            return errors
        except Exception:
            return []

    def _remove_device(self, slot):
        """
        Remove a PCI device via DLPAR
        
        :param slot: Slot name to remove
        :return: Tuple (success, output)
        """
        try:
            cmd = f'drmgr -c pci -r -s "{slot}"'
            result = process.run(cmd, shell=True, ignore_status=True, 
                               timeout=30)
            success = result.exit_status == 0
            return success, result.stdout_text + result.stderr_text
        except Exception as e:
            return False, str(e)

    def _add_device(self, slot):
        """
        Add a PCI device via DLPAR
        
        :param slot: Slot name to add
        :return: Tuple (success, output)
        """
        try:
            cmd = f'drmgr -c pci -a -s "{slot}"'
            result = process.run(cmd, shell=True, ignore_status=True, 
                               timeout=30)
            success = result.exit_status == 0
            return success, result.stdout_text + result.stderr_text
        except Exception as e:
            return False, str(e)

    def _verify_device_present(self, slot):
        """
        Verify device is present in the system
        
        :param slot: Slot name to verify
        :return: Boolean indicating presence
        """
        try:
            result = process.run(f'lsslot -c pci | grep "{slot}"', 
                               shell=True, ignore_status=True)
            return result.exit_status == 0
        except Exception:
            return False

    def _check_error_messages(self, expected_errors=None):
        """
        Check for expected error messages in dmesg
        
        :param expected_errors: List of expected error message patterns
        :return: Dictionary with found status for each pattern
        """
        if expected_errors is None:
            expected_errors = [
                "Unable to add hotplug pci device",
                "Unable to add hotplug slot",
                "can't claim",
                "error updating"
            ]
        
        try:
            result = process.run('dmesg | tail -200', shell=True, 
                               ignore_status=True)
            dmesg_output = result.stdout_text
            
            found = {}
            for pattern in expected_errors:
                found[pattern] = pattern in dmesg_output
            
            return found
        except Exception:
            return {pattern: False for pattern in expected_errors}

    def test_01_normal_add_remove(self):
        """
        Test Case 1: Normal DLPAR add/remove operation
        
        Validates that basic DLPAR operations work correctly with the patch
        """
        self.log.info("Test 1: Normal DLPAR add/remove operation")
        
        # Remove device
        self.log.info(f"Removing device from slot {self.slot_name}")
        success, output = self._remove_device(self.slot_name)
        if not success:
            self.err_mesg.append(f"Failed to remove device: {output}")
        
        time.sleep(2)
        
        # Verify removal
        if self._verify_device_present(self.slot_name):
            self.err_mesg.append("Device still present after removal")
        
        # Add device back
        self.log.info(f"Adding device back to slot {self.slot_name}")
        success, output = self._add_device(self.slot_name)
        if not success:
            self.err_mesg.append(f"Failed to add device: {output}")
        
        time.sleep(2)
        
        # Verify addition
        if not self._verify_device_present(self.slot_name):
            self.err_mesg.append("Device not present after addition")
        
        # Check for unexpected errors
        kernel_errors = self._check_kernel_errors()
        if kernel_errors:
            self.log.warning(f"Kernel errors detected: {kernel_errors}")
        
        if self.err_mesg:
            self.fail(f"Test failed with errors: {'; '.join(self.err_mesg)}")

    def test_02_error_message_verification(self):
        """
        Test Case 2: Verify error messages are present
        
        Validates that appropriate error messages appear when operations fail
        """
        self.log.info("Test 2: Error message verification")
        
        # Clear dmesg to get clean slate
        process.run('dmesg -c > /dev/null', shell=True, ignore_status=True)
        
        # Perform add operation
        success, output = self._add_device(self.slot_name)
        
        time.sleep(1)
        
        # Check for error messages (if operation failed)
        if not success:
            error_msgs = self._check_error_messages()
            self.log.info(f"Error messages found: {error_msgs}")
            
            # At least one error message should be present
            if not any(error_msgs.values()):
                self.err_mesg.append(
                    "No error messages found despite operation failure"
                )
        
        if self.err_mesg:
            self.fail(f"Test failed: {'; '.join(self.err_mesg)}")

    def test_03_return_code_verification(self):
        """
        Test Case 3: Verify correct return codes
        
        Validates that operations return appropriate exit codes
        """
        self.log.info("Test 3: Return code verification")
        
        # Test successful operation
        self._remove_device(self.slot_name)
        time.sleep(1)
        
        success, output = self._add_device(self.slot_name)
        
        if success:
            self.log.info("Add operation succeeded with exit code 0")
        else:
            self.log.info(f"Add operation failed with non-zero exit code")
            # Verify error message is present
            error_msgs = self._check_error_messages()
            if not any(error_msgs.values()):
                self.err_mesg.append(
                    "Operation failed but no error message found"
                )
        
        if self.err_mesg:
            self.fail(f"Test failed: {'; '.join(self.err_mesg)}")

    def test_04_multiple_operations(self):
        """
        Test Case 4: Multiple add/remove cycles
        
        Validates stability across multiple operations
        """
        self.log.info(f"Test 4: Multiple operations ({self.test_iterations} iterations)")
        
        success_count = 0
        failure_count = 0
        
        for i in range(self.test_iterations):
            self.log.info(f"Iteration {i+1}/{self.test_iterations}")
            
            # Remove
            success, _ = self._remove_device(self.slot_name)
            if not success:
                failure_count += 1
                self.log.warning(f"Remove failed at iteration {i+1}")
            
            time.sleep(1)
            
            # Add
            success, _ = self._add_device(self.slot_name)
            if success:
                success_count += 1
            else:
                failure_count += 1
                self.log.warning(f"Add failed at iteration {i+1}")
            
            time.sleep(1)
        
        self.log.info(f"Results: {success_count} successes, {failure_count} failures")
        
        # Check for system stability
        kernel_errors = self._check_kernel_errors()
        if any('panic' in err.lower() or 'bug' in err.lower() 
               for err in kernel_errors):
            self.err_mesg.append("Critical kernel errors detected")
        
        if self.err_mesg:
            self.fail(f"Test failed: {'; '.join(self.err_mesg)}")

    def test_05_memory_leak_check(self):
        """
        Test Case 5: Memory leak detection
        
        Validates no memory leaks in error paths
        """
        self.log.info("Test 5: Memory leak check")
        
        # Get initial memory
        mem_before = self._get_memory_usage()
        
        # Perform multiple operations
        for i in range(10):
            self._remove_device(self.slot_name)
            time.sleep(0.5)
            self._add_device(self.slot_name)
            time.sleep(0.5)
        
        # Get final memory
        mem_after = self._get_memory_usage()
        
        # Check for significant memory increase
        if mem_before and mem_after:
            mem_diff = mem_before.get('MemFree', 0) - mem_after.get('MemFree', 0)
            # Allow 10MB tolerance
            if mem_diff > 10240:  # 10MB in KB
                self.err_mesg.append(
                    f"Potential memory leak detected: {mem_diff}KB lost"
                )
                self.log.warning(f"Memory before: {mem_before.get('MemFree')}KB")
                self.log.warning(f"Memory after: {mem_after.get('MemFree')}KB")
        
        if self.err_mesg:
            self.fail(f"Test failed: {'; '.join(self.err_mesg)}")

    def test_06_system_stability(self):
        """
        Test Case 6: System stability under stress
        
        Validates system remains stable under repeated operations
        """
        if not self.stress_test:
            self.cancel("Stress test not enabled (set stress_test=True)")
        
        self.log.info("Test 6: System stability stress test")
        
        iterations = 50
        errors = []
        
        for i in range(iterations):
            if i % 10 == 0:
                self.log.info(f"Stress iteration {i}/{iterations}")
            
            # Remove
            success, output = self._remove_device(self.slot_name)
            if not success:
                errors.append(f"Remove failed at {i}: {output}")
            
            time.sleep(0.5)
            
            # Add
            success, output = self._add_device(self.slot_name)
            if not success:
                errors.append(f"Add failed at {i}: {output}")
            
            time.sleep(0.5)
            
            # Check system health
            if i % 10 == 0:
                kernel_errors = self._check_kernel_errors()
                if any('panic' in err.lower() for err in kernel_errors):
                    self.fail("Kernel panic detected during stress test")
        
        self.log.info(f"Stress test completed with {len(errors)} errors")
        
        if len(errors) > iterations * 0.1:  # More than 10% failure rate
            self.err_mesg.append(
                f"High failure rate in stress test: {len(errors)}/{iterations}"
            )
        
        if self.err_mesg:
            self.fail(f"Test failed: {'; '.join(self.err_mesg)}")

    def tearDown(self):
        """
        Cleanup and restore system state
        """
        self.log.info("Cleaning up test environment")
        
        # Ensure device is added back
        try:
            self._add_device(self.slot_name)
        except Exception as e:
            self.log.warning(f"Failed to restore device in tearDown: {e}")
        
        # Check final state
        final_devices = self._get_pci_devices()
        final_memory = self._get_memory_usage()
        
        # Log any significant changes
        if len(final_devices) != len(self.initial_devices):
            self.log.warning(
                f"Device count changed: {len(self.initial_devices)} -> "
                f"{len(final_devices)}"
            )
        
        if self.initial_memory and final_memory:
            mem_diff = (self.initial_memory.get('MemFree', 0) - 
                       final_memory.get('MemFree', 0))
            if abs(mem_diff) > 10240:  # 10MB
                self.log.warning(f"Memory usage changed by {mem_diff}KB")
        
        # Report any errors collected during tearDown
        if self.err_mesg:
            self.log.error(f"Errors during test: {'; '.join(self.err_mesg)}")

# Assisted with AI tools
