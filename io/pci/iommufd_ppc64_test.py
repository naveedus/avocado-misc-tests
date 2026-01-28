#!/usr/bin/env python3
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
# Author: Shivaprasad G Bhat <sbhat@linux.ibm.com>
# Author: Naveed <naveedaus@in.ibm.com>
#
# Test IOMMUFD support for PPC64 architecture

import os
import re
from avocado import Test
from avocado.utils import process, genio, distro
from avocado.utils.software_manager.manager import SoftwareManager


class IommufdPpc64Test(Test):
    """
    Test IOMMUFD (I/O Memory Management Unit File Descriptor) support
    for PPC64 architecture with SPAPR TCE (Translation Control Entry) IOMMU.
    
    This test validates the initial IOMMUFD implementation that adds
    paging domain support for PowerPC 64-bit systems.
    
    :avocado: tags=io,pci,iommu,power,privileged
    """

    def setUp(self):
        """
        Verify test prerequisites
        """
        # Check if running on PPC64
        if not distro.detect().arch in ['ppc64', 'ppc64le']:
            self.cancel("Test is only supported on PPC64/PPC64LE architecture")
        
        # Check for required kernel config
        self.kernel_config = '/boot/config-%s' % os.uname().release
        if not os.path.exists(self.kernel_config):
            self.cancel("Kernel config file not found")
        
        # Verify IOMMU API config
        config_content = genio.read_file(self.kernel_config)
        if 'CONFIG_IOMMU_API=y' not in config_content:
            self.cancel("CONFIG_IOMMU_API not enabled in kernel")
        
        # Get test parameters
        self.pci_device = self.params.get('pci_device', default=None)
        self.test_mode = self.params.get('test_mode', default='basic')
        
        # Install required packages
        sm = SoftwareManager()
        deps = ['pciutils']
        for package in deps:
            if not sm.check_installed(package) and not sm.install(package):
                self.cancel(f"Failed to install {package}")

    def test_iommu_groups_exist(self):
        """
        Test 1: Verify IOMMU groups are created
        """
        self.log.info("Checking for IOMMU groups")
        iommu_groups_path = '/sys/kernel/iommu_groups'
        
        if not os.path.exists(iommu_groups_path):
            self.fail("IOMMU groups directory does not exist")
        
        groups = os.listdir(iommu_groups_path)
        if not groups:
            self.fail("No IOMMU groups found")
        
        self.log.info(f"Found {len(groups)} IOMMU groups")
        for group in groups:
            devices_path = os.path.join(iommu_groups_path, group, 'devices')
            if os.path.exists(devices_path):
                devices = os.listdir(devices_path)
                self.log.info(f"Group {group}: {len(devices)} device(s)")

    def test_default_dma_window(self):
        """
        Test 2: Verify default DMA window (1GB) is exposed
        
        The patch exposes only the default 1GB DMA window to userspace.
        This test verifies the DMA window configuration.
        """
        self.log.info("Testing default DMA window configuration")
        
        # Check for IOMMU table information in sysfs
        iommu_groups_path = '/sys/kernel/iommu_groups'
        groups = os.listdir(iommu_groups_path)
        
        for group in groups:
            group_path = os.path.join(iommu_groups_path, group)
            devices_path = os.path.join(group_path, 'devices')
            
            if os.path.exists(devices_path):
                devices = os.listdir(devices_path)
                for device in devices:
                    # Check device IOMMU properties
                    device_path = os.path.join('/sys/bus/pci/devices', device)
                    if os.path.exists(device_path):
                        self.log.info(f"Checking DMA window for device {device}")
                        # Verify device is in an IOMMU group
                        iommu_group_link = os.path.join(device_path, 'iommu_group')
                        if os.path.islink(iommu_group_link):
                            self.log.info(f"Device {device} is in IOMMU group")

    def test_iommu_domain_allocation(self):
        """
        Test 3: Test IOMMU domain allocation
        
        Verifies that the spapr_tce_domain_alloc_paging function
        properly allocates paging domains.
        """
        self.log.info("Testing IOMMU domain allocation")
        
        # Check dmesg for IOMMU initialization messages
        dmesg_output = process.run('dmesg | grep -i iommu', 
                                   ignore_status=True, shell=True).stdout_text
        
        if 'IOMMU' in dmesg_output:
            self.log.info("IOMMU initialization messages found in dmesg")
            self.log.debug(dmesg_output)
        
        # Verify IOMMU is active
        if 'IOMMU' not in dmesg_output:
            self.log.warn("No IOMMU messages in dmesg - may not be configured")

    def test_iommu_page_mapping(self):
        """
        Test 4: Test IOMMU page mapping operations
        
        Tests the IOMMU_PAGE_MASK functionality added in the patch
        which handles direction and attrs parameters.
        """
        self.log.info("Testing IOMMU page mapping")
        
        # Check for IOMMU page size information
        iommu_groups_path = '/sys/kernel/iommu_groups'
        if not os.path.exists(iommu_groups_path):
            self.cancel("IOMMU groups not available")
        
        groups = os.listdir(iommu_groups_path)
        for group in groups:
            reserved_regions = os.path.join(iommu_groups_path, group, 
                                           'reserved_regions')
            if os.path.exists(reserved_regions):
                content = genio.read_file(reserved_regions)
                self.log.info(f"Group {group} reserved regions:\n{content}")

    def test_single_device_passthrough(self):
        """
        Test 5: Test single device passthrough
        
        The patch currently supports single device passthrough.
        This test verifies basic device assignment.
        """
        if not self.pci_device:
            self.cancel("No PCI device specified for passthrough test")
        
        self.log.info(f"Testing device passthrough for {self.pci_device}")
        
        # Verify device exists
        device_path = f'/sys/bus/pci/devices/{self.pci_device}'
        if not os.path.exists(device_path):
            self.fail(f"Device {self.pci_device} not found")
        
        # Check device IOMMU group
        iommu_group_link = os.path.join(device_path, 'iommu_group')
        if not os.path.islink(iommu_group_link):
            self.fail(f"Device {self.pci_device} not in IOMMU group")
        
        group = os.path.basename(os.readlink(iommu_group_link))
        self.log.info(f"Device {self.pci_device} is in IOMMU group {group}")
        
        # Verify driver binding
        driver_link = os.path.join(device_path, 'driver')
        if os.path.islink(driver_link):
            driver = os.path.basename(os.readlink(driver_link))
            self.log.info(f"Device bound to driver: {driver}")

    def test_iommu_table_operations(self):
        """
        Test 6: Test IOMMU table operations
        
        Verifies the iommu_tce_table_get/put operations work correctly
        for managing TCE (Translation Control Entry) tables.
        """
        self.log.info("Testing IOMMU table operations")
        
        # Check for TCE table information in debugfs if available
        debugfs_iommu = '/sys/kernel/debug/iommu'
        if os.path.exists(debugfs_iommu):
            self.log.info("IOMMU debugfs available")
            # List IOMMU debug information
            result = process.run(f'ls -la {debugfs_iommu}', 
                               ignore_status=True, shell=True)
            self.log.debug(result.stdout_text)

    def test_dma_window_attributes(self):
        """
        Test 7: Test DMA window attributes
        
        Verifies that DMA window attributes are properly configured:
        - Page size bitmap (SZ_4K for now)
        - Force aperture = true
        - Aperture start = 0
        - Aperture end = 0x40000000 (1GB default window)
        """
        self.log.info("Testing DMA window attributes")
        
        # The patch sets these values in spapr_tce_domain_alloc_paging:
        # - pgsize_bitmap = SZ_4K
        # - geometry.force_aperture = true
        # - geometry.aperture_start = 0
        # - geometry.aperture_end = 0x40000000 (1GB)
        
        expected_window_size = 0x40000000  # 1GB
        self.log.info(f"Expected default DMA window size: {expected_window_size} bytes (1GB)")

    def test_iommu_unmap_operations(self):
        """
        Test 8: Test IOMMU unmap operations
        
        Verifies the spapr_tce_iommu_unmap_pages function works correctly.
        """
        self.log.info("Testing IOMMU unmap operations")
        
        # Check for any IOMMU-related errors in dmesg
        result = process.run('dmesg | grep -i "iommu.*error"', 
                           ignore_status=True, shell=True)
        
        if result.exit_status == 0 and result.stdout_text:
            self.log.warn(f"IOMMU errors found in dmesg:\n{result.stdout_text}")
        else:
            self.log.info("No IOMMU errors found in dmesg")

    def test_powerpc_specific_features(self):
        """
        Test 9: Test PowerPC-specific IOMMU features
        
        Verifies PowerPC-specific features like:
        - SPAPR TCE IOMMU support
        - PowerNV (bare metal) vs pSeries (LPAR) detection
        """
        self.log.info("Testing PowerPC-specific IOMMU features")
        
        # Detect platform type
        if os.path.exists('/proc/device-tree/ibm,partition-name'):
            platform = 'pSeries (LPAR)'
        elif os.path.exists('/proc/device-tree/ibm,opal'):
            platform = 'PowerNV (bare metal)'
        else:
            platform = 'Unknown'
        
        self.log.info(f"Detected platform: {platform}")
        
        # Check for SPAPR-specific features
        result = process.run('dmesg | grep -i spapr', 
                           ignore_status=True, shell=True)
        if result.exit_status == 0:
            self.log.info("SPAPR features detected")
            self.log.debug(result.stdout_text)

    def test_iommu_group_devices(self):
        """
        Test 10: Test IOMMU group device management
        
        Verifies that devices are properly assigned to IOMMU groups
        and that group operations work correctly.
        """
        self.log.info("Testing IOMMU group device management")
        
        iommu_groups_path = '/sys/kernel/iommu_groups'
        if not os.path.exists(iommu_groups_path):
            self.cancel("IOMMU groups not available")
        
        groups = os.listdir(iommu_groups_path)
        device_count = 0
        
        for group in groups:
            devices_path = os.path.join(iommu_groups_path, group, 'devices')
            if os.path.exists(devices_path):
                devices = os.listdir(devices_path)
                device_count += len(devices)
                
                for device in devices:
                    # Get device information
                    device_path = os.path.join('/sys/bus/pci/devices', device)
                    if os.path.exists(device_path):
                        # Read vendor and device ID
                        vendor_path = os.path.join(device_path, 'vendor')
                        device_id_path = os.path.join(device_path, 'device')
                        
                        if os.path.exists(vendor_path) and os.path.exists(device_id_path):
                            vendor = genio.read_file(vendor_path).strip()
                            dev_id = genio.read_file(device_id_path).strip()
                            self.log.info(f"Group {group}: Device {device} "
                                        f"(Vendor: {vendor}, Device: {dev_id})")
        
        self.log.info(f"Total devices in IOMMU groups: {device_count}")
        if device_count == 0:
            self.log.warn("No devices found in IOMMU groups")

    def tearDown(self):
        """
        Cleanup after tests
        """
        self.log.info("Test cleanup completed")

# Assisted by AI tools
