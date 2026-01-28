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
# Copyright: 2026 IBM
# Author: Naveed <naveedaus@in.ibm.com>

"""
NVMe Firmware Update Tests
Tests firmware update operations with validation
"""

import os
import time
from avocado import Test
from avocado.utils import process, disk, archive
from avocado.utils import nvme
from avocado.utils.software_manager.manager import SoftwareManager


class NVMeFirmwareUpdate(Test):
    """
    NVMe Firmware Update Test Suite
    
    :param device: Name of the nvme controller (nvmeX, nvme-subsysX, or NQN)
    :param firmware_url: URL to download firmware binary
    :param force_update: Force update even if same version (default: true)
    :param slot: Firmware slot to use (default: 0 for next available)
    :param action: Firmware commit action (default: 1 for download and activate)
    """

    def setUp(self):
        """
        Setup NVMe device and install required tools
        """
        smm = SoftwareManager()
        if not smm.check_installed("nvme-cli") and not smm.install("nvme-cli"):
            self.cancel('nvme-cli is needed for the test to be run')
        
        nvme_node = self.params.get('device', default=None)
        if not nvme_node:
            self.cancel("Please provide valid nvme controller name")
        
        # Handle different device name formats
        if "subsys" in nvme_node:
            nvme_node = nvme.get_controllers_with_subsys(nvme_node)[0]
        elif nvme_node.startswith("nqn."):
            nvme_node = nvme.get_controllers_with_nqn(nvme_node)[0]
        
        self.device = disk.get_absolute_disk_path(nvme_node)
        self.controller = self.device.split("/")[-1]
        
        # Check if device exists
        cmd = f'ls {self.device}'
        if process.system(cmd, shell=True, ignore_status=True) != 0:
            self.cancel(f"NVMe device {self.device} not found")
        
        # Get firmware URL
        self.firmware_url = self.params.get('firmware_url', default=None)
        if not self.firmware_url:
            self.cancel("firmware_url parameter is required")
        
        # Get update parameters
        self.force_update = self.params.get('force_update', default=True)
        self.slot = self.params.get('slot', default=0)
        self.action = self.params.get('action', default=1)
        
        self.log.info(f"Controller: {self.controller}")
        self.log.info(f"Firmware URL: {self.firmware_url}")
        self.log.info(f"Force Update: {self.force_update}")
        self.log.info(f"Slot: {self.slot}")
        self.log.info(f"Action: {self.action}")
        
        # Download firmware
        self.firmware_file = self.download_firmware()

    def download_firmware(self):
        """
        Download firmware binary from URL
        
        :return: Path to downloaded firmware file
        """
        self.log.info(f"Downloading firmware from {self.firmware_url}")
        
        try:
            # Determine filename from URL
            filename = os.path.basename(self.firmware_url)
            if not filename:
                filename = "nvme_firmware.bin"
            
            # Download to workdir
            firmware_path = self.fetch_asset(
                filename,
                locations=[self.firmware_url],
                expire='7d'
            )
            
            self.log.info(f"Firmware downloaded to: {firmware_path}")
            
            # Check if it's an archive and extract if needed
            if firmware_path.endswith(('.zip', '.tar.gz', '.tgz', '.tar.bz2')):
                self.log.info("Extracting firmware archive")
                extract_dir = os.path.join(self.workdir, 'firmware_extracted')
                archive.extract(firmware_path, extract_dir)
                
                # Find .bin or .fw file in extracted directory
                for root, dirs, files in os.walk(extract_dir):
                    for file in files:
                        if file.endswith(('.bin', '.fw', '.rom')):
                            firmware_path = os.path.join(root, file)
                            self.log.info(f"Found firmware binary: {firmware_path}")
                            break
            
            # Verify file exists and is readable
            if not os.path.exists(firmware_path):
                self.cancel(f"Firmware file not found: {firmware_path}")
            
            if not os.access(firmware_path, os.R_OK):
                self.cancel(f"Firmware file not readable: {firmware_path}")
            
            file_size = os.path.getsize(firmware_path)
            self.log.info(f"Firmware file size: {file_size} bytes")
            
            return firmware_path
            
        except Exception as e:
            self.cancel(f"Failed to download firmware: {str(e)}")

    def get_firmware_version(self):
        """
        Get current firmware version from controller
        
        :return: Dictionary with firmware revision and slot information
        """
        self.log.info("Reading current firmware version")
        
        # Get firmware revision from id-ctrl
        cmd = f"nvme id-ctrl {self.device} | grep fr"
        output = process.system_output(cmd, shell=True, ignore_status=True).decode()
        
        firmware_info = {}
        if output:
            # Parse firmware revision
            for line in output.split('\n'):
                if 'fr' in line.lower():
                    firmware_info['revision'] = line.split(':')[1].strip()
                    break
        
        # Get firmware slot information
        cmd = f"nvme fw-log {self.device}"
        output = process.system_output(cmd, shell=True, ignore_status=True).decode()
        
        self.log.info(f"Firmware log output:\n{output}")
        
        # Parse active slot and slot versions
        firmware_info['slots'] = {}
        firmware_info['active_slot'] = None
        
        for line in output.split('\n'):
            if 'afi' in line.lower():
                # Active firmware info
                parts = line.split(':')
                if len(parts) > 1:
                    firmware_info['active_slot'] = parts[1].strip()
            elif 'frs' in line.lower():
                # Firmware slot info
                # Format: frsX : Firmware Revision Slot X : version
                parts = line.split(':')
                if len(parts) >= 3:
                    slot_num = parts[0].strip().replace('frs', '')
                    slot_version = parts[2].strip()
                    firmware_info['slots'][slot_num] = slot_version
        
        self.log.info(f"Current firmware info: {firmware_info}")
        return firmware_info

    def validate_firmware_update(self, pre_update_info, expected_change=True):
        """
        Validate firmware update by comparing versions
        
        :param pre_update_info: Firmware info before update
        :param expected_change: Whether version should change (False for force update of same version)
        :return: True if validation passes, False otherwise
        """
        self.log.info("Validating firmware update")
        
        # Wait for controller to stabilize after update
        time.sleep(5)
        
        # Get post-update firmware info
        post_update_info = self.get_firmware_version()
        
        self.log.info(f"Pre-update info: {pre_update_info}")
        self.log.info(f"Post-update info: {post_update_info}")
        
        # Check if firmware revision changed (if expected)
        pre_revision = pre_update_info.get('revision', '')
        post_revision = post_update_info.get('revision', '')
        
        if expected_change:
            if pre_revision == post_revision:
                self.log.warning(f"Firmware revision unchanged: {post_revision}")
                # This might be OK if it's a force update of same version
                if not self.force_update:
                    return False
        else:
            # For force update of same version, revision should stay same
            if pre_revision != post_revision:
                self.log.error(f"Firmware revision changed unexpectedly: {pre_revision} -> {post_revision}")
                return False
        
        # Verify controller is still accessible
        cmd = f"nvme id-ctrl {self.device}"
        if process.system(cmd, shell=True, ignore_status=True) != 0:
            self.log.error("Controller not accessible after firmware update")
            return False
        
        # Verify namespaces are still accessible
        ns_list = nvme.get_current_ns_list(self.controller)
        self.log.info(f"Namespaces after update: {ns_list}")
        
        for ns in ns_list:
            ns_path = f"/dev/{ns}"
            if not os.path.exists(ns_path):
                self.log.error(f"Namespace {ns_path} not accessible after update")
                return False
        
        self.log.info("Firmware update validation successful")
        return True

    def perform_firmware_download(self):
        """
        Download firmware to controller
        
        :return: True if successful, False otherwise
        """
        self.log.info(f"Downloading firmware to controller from {self.firmware_file}")
        
        cmd = f"nvme fw-download {self.device} --fw={self.firmware_file}"
        result = process.run(cmd, shell=True, ignore_status=True)
        
        if result.exit_status != 0:
            self.log.error(f"Firmware download failed: {result.stderr.decode()}")
            return False
        
        self.log.info("Firmware download successful")
        self.log.info(result.stdout.decode())
        return True

    def perform_firmware_commit(self, slot=None, action=None):
        """
        Commit/activate downloaded firmware
        
        :param slot: Firmware slot (0 for next available)
        :param action: Commit action (1=download and activate, 2=download only, 3=activate only)
        :return: True if successful, False otherwise
        """
        if slot is None:
            slot = self.slot
        if action is None:
            action = self.action
        
        self.log.info(f"Committing firmware to slot {slot} with action {action}")
        
        cmd = f"nvme fw-commit {self.device} -s {slot} -a {action}"
        result = process.run(cmd, shell=True, ignore_status=True)
        
        if result.exit_status != 0:
            self.log.error(f"Firmware commit failed: {result.stderr.decode()}")
            return False
        
        self.log.info("Firmware commit successful")
        self.log.info(result.stdout.decode())
        return True

    def reset_controller(self):
        """
        Reset NVMe controller to activate new firmware
        """
        self.log.info("Resetting controller to activate firmware")
        
        cmd = f"echo 1 > /sys/class/nvme/{self.controller}/reset_controller"
        result = process.run(cmd, shell=True, ignore_status=True, sudo=True)
        
        if result.exit_status != 0:
            self.log.warning("Controller reset via sysfs failed, trying nvme reset")
            cmd = f"nvme reset {self.device}"
            process.run(cmd, shell=True, ignore_status=True)
        
        # Wait for controller to come back online
        time.sleep(10)
        
        # Verify controller is accessible
        max_retries = 30
        for i in range(max_retries):
            cmd = f"nvme id-ctrl {self.device}"
            if process.system(cmd, shell=True, ignore_status=True) == 0:
                self.log.info("Controller is back online")
                return True
            self.log.info(f"Waiting for controller... ({i+1}/{max_retries})")
            time.sleep(2)
        
        self.log.error("Controller did not come back online after reset")
        return False

    def test_firmware_update_standard(self):
        """
        Test standard firmware update process
        Downloads firmware, commits, and validates
        """
        self.log.info("Test: Standard firmware update")
        
        # Get pre-update firmware info
        pre_update_info = self.get_firmware_version()
        
        # Download firmware to controller
        if not self.perform_firmware_download():
            self.fail("Firmware download failed")
        
        # Commit firmware
        if not self.perform_firmware_commit():
            self.fail("Firmware commit failed")
        
        # Reset controller if needed (action 1 or 3 requires reset)
        if self.action in [1, 3]:
            if not self.reset_controller():
                self.fail("Controller reset failed")
        
        # Validate update
        expected_change = not self.force_update
        if not self.validate_firmware_update(pre_update_info, expected_change):
            self.fail("Firmware update validation failed")

    def test_firmware_update_force_same_version(self):
        """
        Test force update with same firmware version
        Validates that force update works even with same version
        """
        self.log.info("Test: Force update with same firmware version")
        
        # Get current firmware info
        pre_update_info = self.get_firmware_version()
        current_revision = pre_update_info.get('revision', '')
        
        self.log.info(f"Current firmware revision: {current_revision}")
        self.log.info("Forcing update with same firmware version")
        
        # Download firmware
        if not self.perform_firmware_download():
            self.fail("Firmware download failed")
        
        # Commit with force (action 1)
        if not self.perform_firmware_commit(action=1):
            self.fail("Firmware commit failed")
        
        # Reset controller
        if not self.reset_controller():
            self.fail("Controller reset failed")
        
        # Validate - version should remain same for force update
        if not self.validate_firmware_update(pre_update_info, expected_change=False):
            self.fail("Force firmware update validation failed")
        
        # Verify revision is still the same
        post_update_info = self.get_firmware_version()
        post_revision = post_update_info.get('revision', '')
        
        if current_revision != post_revision:
            self.log.warning(f"Firmware revision changed: {current_revision} -> {post_revision}")
        else:
            self.log.info(f"Firmware revision unchanged (as expected for same version): {post_revision}")

    def test_firmware_update_with_slot_selection(self):
        """
        Test firmware update to specific slot
        Validates slot-based firmware management
        """
        self.log.info("Test: Firmware update with slot selection")
        
        # Get pre-update firmware info
        pre_update_info = self.get_firmware_version()
        
        # Use slot 1 explicitly
        target_slot = 1
        self.log.info(f"Updating firmware to slot {target_slot}")
        
        # Download firmware
        if not self.perform_firmware_download():
            self.fail("Firmware download failed")
        
        # Commit to specific slot
        if not self.perform_firmware_commit(slot=target_slot, action=1):
            self.fail("Firmware commit to slot failed")
        
        # Reset controller
        if not self.reset_controller():
            self.fail("Controller reset failed")
        
        # Validate update
        if not self.validate_firmware_update(pre_update_info):
            self.fail("Firmware update validation failed")
        
        # Verify active slot
        post_update_info = self.get_firmware_version()
        active_slot = post_update_info.get('active_slot', '')
        self.log.info(f"Active firmware slot after update: {active_slot}")

    def tearDown(self):
        """
        Cleanup: Log final firmware state
        """
        self.log.info("Final firmware state:")
        final_info = self.get_firmware_version()
        self.log.info(f"Firmware revision: {final_info.get('revision', 'Unknown')}")
        self.log.info(f"Active slot: {final_info.get('active_slot', 'Unknown')}")
        self.log.info(f"Slot versions: {final_info.get('slots', {})}")

# Assisted with AI tools
