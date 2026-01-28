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
NVMe Namespace Creation Tests
Tests various namespace creation scenarios with validation
"""

import os
import time
from avocado import Test
from avocado.utils import process, disk
from avocado.utils import nvme
from avocado.utils.software_manager.manager import SoftwareManager


class NVMeCreateNamespace(Test):
    """
    NVMe Namespace Creation Test Suite
    
    :param device: Name of the nvme controller (nvmeX, nvme-subsysX, or NQN)
    :param namespace_count: Number of namespaces to create for equal size test
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
        
        # Get controller properties
        self.total_capacity = self.get_total_capacity()
        self.block_size = self.get_block_size()
        self.max_ns_count = self.get_max_ns_count()
        
        self.log.info(f"Controller: {self.controller}")
        self.log.info(f"Total Capacity: {self.total_capacity} bytes")
        self.log.info(f"Block Size: {self.block_size} bytes")
        self.log.info(f"Max Namespace Count: {self.max_ns_count}")

    def get_total_capacity(self):
        """Get total capacity of NVMe controller"""
        cmd = f"nvme id-ctrl {self.device} | grep tnvmcap"
        output = process.system_output(cmd, shell=True, ignore_status=True).decode()
        if output:
            return int(output.split(':')[1].strip())
        return 0

    def get_block_size(self):
        """Get block size of NVMe controller"""
        cmd = f"nvme id-ctrl {self.device} | grep 'lbaf  0'"
        output = process.system_output(cmd, shell=True, ignore_status=True).decode()
        if output and 'ds:' in output:
            ds_value = int(output.split('ds:')[1].split()[0])
            return 2 ** ds_value
        return 512  # Default block size

    def get_max_ns_count(self):
        """Get maximum namespace count supported"""
        cmd = f"nvme id-ctrl {self.device} | grep nn"
        output = process.system_output(cmd, shell=True, ignore_status=True).decode()
        if output:
            return int(output.split(':')[1].strip())
        return 1

    def validate_namespace_creation(self, expected_count):
        """
        Validate that namespaces were created successfully
        
        :param expected_count: Expected number of namespaces
        :return: True if validation passes, False otherwise
        """
        # Wait for namespaces to be visible
        time.sleep(2)
        
        # Check nvme list command
        cmd = "nvme list"
        output = process.system_output(cmd, shell=True, ignore_status=True).decode()
        self.log.info(f"nvme list output:\n{output}")
        
        # Count namespaces for this controller
        ns_count = 0
        for line in output.split('\n'):
            if self.controller in line:
                ns_count += 1
        
        if ns_count != expected_count:
            self.log.error(f"Expected {expected_count} namespaces, found {ns_count}")
            return False
        
        # Check sysfs entries
        sysfs_path = f"/sys/class/nvme/{self.controller}"
        if os.path.exists(sysfs_path):
            ns_dirs = [d for d in os.listdir(sysfs_path) if d.startswith(f"{self.controller}n")]
            self.log.info(f"Sysfs namespaces: {ns_dirs}")
            if len(ns_dirs) != expected_count:
                self.log.error(f"Sysfs shows {len(ns_dirs)} namespaces, expected {expected_count}")
                return False
        
        # Verify each namespace is accessible
        current_ns_list = nvme.get_current_ns_list(self.controller)
        self.log.info(f"Current namespace list: {current_ns_list}")
        
        for ns in current_ns_list:
            ns_path = f"/dev/{ns}"
            if not os.path.exists(ns_path):
                self.log.error(f"Namespace device {ns_path} not found")
                return False
            
            # Try to read namespace info
            cmd = f"nvme id-ns {ns_path}"
            if process.system(cmd, shell=True, ignore_status=True) != 0:
                self.log.error(f"Failed to read namespace info for {ns_path}")
                return False
        
        self.log.info(f"Successfully validated {expected_count} namespaces")
        return True

    def cleanup_namespaces(self):
        """Delete all existing namespaces"""
        self.log.info("Cleaning up existing namespaces")
        nvme.delete_all_ns(self.controller)
        time.sleep(2)
        
        # Verify cleanup
        current_ns = nvme.get_current_ns_list(self.controller)
        if current_ns:
            self.log.warning(f"Namespaces still exist after cleanup: {current_ns}")

    def test_create_full_capacity_namespace(self):
        """
        Test creating a single namespace with full capacity
        Validates namespace appears in nvme list and sysfs
        """
        self.log.info("Test: Create full capacity namespace")
        
        # Cleanup existing namespaces
        self.cleanup_namespaces()
        
        # Create full capacity namespace
        self.log.info("Creating full capacity namespace")
        nvme.create_full_capacity_ns(self.controller, shared_ns=False)
        
        # Rescan to detect new namespace
        cmd = f"echo 1 > /sys/class/nvme/{self.controller}/rescan_controller"
        process.system(cmd, shell=True, ignore_status=True, sudo=True)
        
        # Validate creation
        if not self.validate_namespace_creation(1):
            self.fail("Full capacity namespace creation validation failed")
        
        # Verify capacity
        ns_list = nvme.get_current_ns_list(self.controller)
        if ns_list:
            ns_path = f"/dev/{ns_list[0]}"
            cmd = f"nvme id-ns {ns_path} | grep nsze"
            output = process.system_output(cmd, shell=True).decode()
            self.log.info(f"Namespace size: {output}")

    def test_create_max_namespaces(self):
        """
        Test creating maximum number of namespaces
        Each namespace gets equal capacity (60% of total divided equally)
        """
        self.log.info(f"Test: Create maximum namespaces (max: {self.max_ns_count})")
        
        # Cleanup existing namespaces
        self.cleanup_namespaces()
        
        # Calculate blocks per namespace
        max_ns_blocks = self.total_capacity // self.block_size
        max_ns_blocks_considered = int(60 * max_ns_blocks / 100)
        per_ns_blocks = max_ns_blocks_considered // self.max_ns_count
        
        self.log.info(f"Creating {self.max_ns_count} namespaces")
        self.log.info(f"Blocks per namespace: {per_ns_blocks}")
        
        # Get controller ID for attachment
        cmd = f"nvme id-ctrl {self.device} | grep cntlid"
        output = process.system_output(cmd, shell=True).decode()
        controller_id = output.split(':')[1].strip()
        
        # Create namespaces
        for ns_id in range(1, self.max_ns_count + 1):
            self.log.info(f"Creating namespace {ns_id}/{self.max_ns_count}")
            
            # Create namespace
            cmd = f"nvme create-ns {self.device} --nsze={int(per_ns_blocks)} --ncap={int(per_ns_blocks)} --flbas=0 --dps=0"
            if process.system(cmd, shell=True, ignore_status=True) != 0:
                self.fail(f"Failed to create namespace {ns_id}")
            
            # Attach namespace
            cmd = f"nvme attach-ns {self.device} --namespace-id={ns_id} --controllers={controller_id}"
            if process.system(cmd, shell=True, ignore_status=True) != 0:
                self.fail(f"Failed to attach namespace {ns_id}")
        
        # Rescan controller
        cmd = f"echo 1 > /sys/class/nvme/{self.controller}/rescan_controller"
        process.system(cmd, shell=True, ignore_status=True, sudo=True)
        
        # Validate all namespaces created
        if not self.validate_namespace_creation(self.max_ns_count):
            self.fail("Maximum namespace creation validation failed")

    def test_create_equal_size_namespaces(self):
        """
        Test creating specified number of equal-sized namespaces
        Uses namespace_count parameter from YAML
        """
        ns_count = self.params.get('namespace_count', default=4)
        self.log.info(f"Test: Create {ns_count} equal-sized namespaces")
        
        if ns_count > self.max_ns_count:
            self.cancel(f"Requested {ns_count} namespaces exceeds maximum {self.max_ns_count}")
        
        # Cleanup existing namespaces
        self.cleanup_namespaces()
        
        # Create namespaces using utility function
        self.log.info(f"Creating {ns_count} equal-sized namespaces")
        nvme.create_namespaces(self.controller, ns_count, shared_ns=False)
        
        # Rescan controller
        cmd = f"echo 1 > /sys/class/nvme/{self.controller}/rescan_controller"
        process.system(cmd, shell=True, ignore_status=True, sudo=True)
        
        # Validate creation
        if not self.validate_namespace_creation(ns_count):
            self.fail(f"Equal-sized namespace creation validation failed for {ns_count} namespaces")
        
        # Verify all namespaces have similar size
        ns_list = nvme.get_current_ns_list(self.controller)
        sizes = []
        for ns in ns_list:
            ns_path = f"/dev/{ns}"
            cmd = f"nvme id-ns {ns_path} | grep nsze"
            output = process.system_output(cmd, shell=True).decode()
            size = int(output.split(':')[1].strip())
            sizes.append(size)
            self.log.info(f"{ns}: {size} blocks")
        
        # Check if sizes are approximately equal (within 10% variance)
        avg_size = sum(sizes) / len(sizes)
        for size in sizes:
            variance = abs(size - avg_size) / avg_size * 100
            if variance > 10:
                self.log.warning(f"Namespace size variance: {variance:.2f}%")

    def tearDown(self):
        """
        Cleanup: Optionally restore to single full capacity namespace
        """
        restore = self.params.get('restore_full_capacity', default=False)
        if restore:
            self.log.info("Restoring to full capacity namespace")
            self.cleanup_namespaces()
            nvme.create_full_capacity_ns(self.controller, shared_ns=False)

# Assisted with AI tools
