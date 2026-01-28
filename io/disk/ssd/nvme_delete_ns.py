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
NVMe Namespace Deletion Tests
Tests various namespace deletion scenarios with validation
"""

import os
import time
from avocado import Test
from avocado.utils import process, disk
from avocado.utils import nvme
from avocado.utils.software_manager.manager import SoftwareManager


class NVMeDeleteNamespace(Test):
    """
    NVMe Namespace Deletion Test Suite
    
    :param device: Name of the nvme controller (nvmeX, nvme-subsysX, or NQN)
    :param namespace_id: Specific namespace ID to delete (for single deletion test)
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
        
        self.log.info(f"Controller: {self.controller}")

    def get_namespace_list(self):
        """
        Get list of current namespaces
        
        :return: List of namespace IDs
        """
        return nvme.get_current_ns_list(self.controller)

    def validate_namespace_deletion(self, deleted_ns_ids):
        """
        Validate that namespaces were deleted successfully
        
        :param deleted_ns_ids: List of namespace IDs that should be deleted
        :return: True if validation passes, False otherwise
        """
        # Wait for changes to propagate
        time.sleep(2)
        
        # Get current namespace list
        current_ns_list = self.get_namespace_list()
        self.log.info(f"Current namespaces after deletion: {current_ns_list}")
        
        # Check that deleted namespaces are not in the list
        for ns_id in deleted_ns_ids:
            ns_name = f"{self.controller}n{ns_id}"
            if ns_name in current_ns_list:
                self.log.error(f"Namespace {ns_name} still exists after deletion")
                return False
            
            # Check device node doesn't exist
            ns_path = f"/dev/{ns_name}"
            if os.path.exists(ns_path):
                self.log.error(f"Device node {ns_path} still exists after deletion")
                return False
            
            # Check sysfs entry doesn't exist
            sysfs_path = f"/sys/class/nvme/{self.controller}/{ns_name}"
            if os.path.exists(sysfs_path):
                self.log.error(f"Sysfs entry {sysfs_path} still exists after deletion")
                return False
        
        # Verify nvme list doesn't show deleted namespaces
        cmd = "nvme list"
        output = process.system_output(cmd, shell=True, ignore_status=True).decode()
        for ns_id in deleted_ns_ids:
            ns_name = f"{self.controller}n{ns_id}"
            if ns_name in output:
                self.log.error(f"Namespace {ns_name} still appears in nvme list")
                return False
        
        self.log.info(f"Successfully validated deletion of namespaces: {deleted_ns_ids}")
        return True

    def create_test_namespaces(self, count=4):
        """
        Create test namespaces for deletion tests
        
        :param count: Number of namespaces to create
        :return: List of created namespace IDs
        """
        self.log.info(f"Creating {count} test namespaces")
        
        # Delete existing namespaces first
        nvme.delete_all_ns(self.controller)
        time.sleep(2)
        
        # Create new namespaces
        nvme.create_namespaces(self.controller, count, shared_ns=False)
        
        # Rescan controller
        cmd = f"echo 1 > /sys/class/nvme/{self.controller}/rescan_controller"
        process.system(cmd, shell=True, ignore_status=True, sudo=True)
        time.sleep(2)
        
        # Get created namespace IDs
        ns_list = self.get_namespace_list()
        self.log.info(f"Created namespaces: {ns_list}")
        
        # Extract namespace IDs
        ns_ids = []
        for ns in ns_list:
            # Extract number from nvmeXnY format
            ns_id = ns.split('n')[-1]
            ns_ids.append(ns_id)
        
        return ns_ids

    def test_delete_single_namespace(self):
        """
        Test deleting a single specific namespace
        Validates namespace is removed from all system locations
        """
        self.log.info("Test: Delete single namespace")
        
        # Create test namespaces
        ns_ids = self.create_test_namespaces(count=3)
        
        if not ns_ids:
            self.fail("Failed to create test namespaces")
        
        # Select middle namespace to delete
        ns_to_delete = ns_ids[len(ns_ids) // 2]
        self.log.info(f"Deleting namespace ID: {ns_to_delete}")
        
        # Delete the namespace
        cmd = f"nvme delete-ns {self.device} -n {ns_to_delete}"
        if process.system(cmd, shell=True, ignore_status=True) != 0:
            self.fail(f"Failed to delete namespace {ns_to_delete}")
        
        # Rescan controller
        cmd = f"echo 1 > /sys/class/nvme/{self.controller}/rescan_controller"
        process.system(cmd, shell=True, ignore_status=True, sudo=True)
        
        # Validate deletion
        if not self.validate_namespace_deletion([ns_to_delete]):
            self.fail(f"Single namespace deletion validation failed for namespace {ns_to_delete}")
        
        # Verify other namespaces still exist
        remaining_ns = self.get_namespace_list()
        expected_count = len(ns_ids) - 1
        if len(remaining_ns) != expected_count:
            self.fail(f"Expected {expected_count} remaining namespaces, found {len(remaining_ns)}")

    def test_delete_all_namespaces(self):
        """
        Test deleting all namespaces from controller
        Validates all namespaces are removed
        """
        self.log.info("Test: Delete all namespaces")
        
        # Create test namespaces
        ns_ids = self.create_test_namespaces(count=5)
        
        if not ns_ids:
            self.fail("Failed to create test namespaces")
        
        self.log.info(f"Deleting all {len(ns_ids)} namespaces")
        
        # Delete all namespaces
        nvme.delete_all_ns(self.controller)
        
        # Rescan controller
        cmd = f"echo 1 > /sys/class/nvme/{self.controller}/rescan_controller"
        process.system(cmd, shell=True, ignore_status=True, sudo=True)
        
        # Validate all deleted
        if not self.validate_namespace_deletion(ns_ids):
            self.fail("Delete all namespaces validation failed")
        
        # Verify no namespaces remain
        remaining_ns = self.get_namespace_list()
        if remaining_ns:
            self.fail(f"Namespaces still exist after delete all: {remaining_ns}")

    def test_delete_multiple_specific_namespaces(self):
        """
        Test deleting multiple specific namespaces
        Validates only specified namespaces are deleted
        """
        self.log.info("Test: Delete multiple specific namespaces")
        
        # Create test namespaces
        ns_ids = self.create_test_namespaces(count=6)
        
        if len(ns_ids) < 3:
            self.fail("Need at least 3 namespaces for this test")
        
        # Select alternate namespaces to delete (e.g., 1st, 3rd, 5th)
        ns_to_delete = [ns_ids[i] for i in range(0, len(ns_ids), 2)]
        ns_to_keep = [ns_ids[i] for i in range(1, len(ns_ids), 2)]
        
        self.log.info(f"Deleting namespaces: {ns_to_delete}")
        self.log.info(f"Keeping namespaces: {ns_to_keep}")
        
        # Delete selected namespaces
        for ns_id in ns_to_delete:
            cmd = f"nvme delete-ns {self.device} -n {ns_id}"
            if process.system(cmd, shell=True, ignore_status=True) != 0:
                self.fail(f"Failed to delete namespace {ns_id}")
        
        # Rescan controller
        cmd = f"echo 1 > /sys/class/nvme/{self.controller}/rescan_controller"
        process.system(cmd, shell=True, ignore_status=True, sudo=True)
        
        # Validate deleted namespaces are gone
        if not self.validate_namespace_deletion(ns_to_delete):
            self.fail("Multiple namespace deletion validation failed")
        
        # Verify kept namespaces still exist
        current_ns = self.get_namespace_list()
        for ns_id in ns_to_keep:
            ns_name = f"{self.controller}n{ns_id}"
            if ns_name not in current_ns:
                self.fail(f"Namespace {ns_name} was incorrectly deleted")

    def test_delete_and_recreate_namespace(self):
        """
        Test deleting a namespace and recreating it with same ID
        Validates namespace can be reused after deletion
        """
        self.log.info("Test: Delete and recreate namespace")
        
        # Create initial namespace
        ns_ids = self.create_test_namespaces(count=1)
        
        if not ns_ids:
            self.fail("Failed to create test namespace")
        
        ns_id = ns_ids[0]
        self.log.info(f"Initial namespace ID: {ns_id}")
        
        # Get initial namespace info
        ns_path = f"/dev/{self.controller}n{ns_id}"
        cmd = f"nvme id-ns {ns_path} | grep nsze"
        initial_size = process.system_output(cmd, shell=True).decode()
        self.log.info(f"Initial namespace size: {initial_size}")
        
        # Delete the namespace
        self.log.info(f"Deleting namespace {ns_id}")
        cmd = f"nvme delete-ns {self.device} -n {ns_id}"
        if process.system(cmd, shell=True, ignore_status=True) != 0:
            self.fail(f"Failed to delete namespace {ns_id}")
        
        # Rescan and validate deletion
        cmd = f"echo 1 > /sys/class/nvme/{self.controller}/rescan_controller"
        process.system(cmd, shell=True, ignore_status=True, sudo=True)
        
        if not self.validate_namespace_deletion([ns_id]):
            self.fail("Namespace deletion validation failed")
        
        # Recreate namespace with same ID
        self.log.info(f"Recreating namespace {ns_id}")
        nvme.create_full_capacity_ns(self.controller, shared_ns=False)
        
        # Rescan controller
        cmd = f"echo 1 > /sys/class/nvme/{self.controller}/rescan_controller"
        process.system(cmd, shell=True, ignore_status=True, sudo=True)
        time.sleep(2)
        
        # Verify recreation
        new_ns_list = self.get_namespace_list()
        if not new_ns_list:
            self.fail("Failed to recreate namespace")
        
        self.log.info(f"Recreated namespace: {new_ns_list[0]}")
        
        # Verify new namespace is accessible
        new_ns_path = f"/dev/{new_ns_list[0]}"
        cmd = f"nvme id-ns {new_ns_path}"
        if process.system(cmd, shell=True, ignore_status=True) != 0:
            self.fail("Recreated namespace is not accessible")

    def tearDown(self):
        """
        Cleanup: Restore to single full capacity namespace
        """
        restore = self.params.get('restore_full_capacity', default=True)
        if restore:
            self.log.info("Restoring to full capacity namespace")
            nvme.delete_all_ns(self.controller)
            time.sleep(2)
            nvme.create_full_capacity_ns(self.controller, shared_ns=False)
            cmd = f"echo 1 > /sys/class/nvme/{self.controller}/rescan_controller"
            process.system(cmd, shell=True, ignore_status=True, sudo=True)

# Assisted with AI tools
