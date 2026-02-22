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
# Copyright: 2026 Naveed AUS, IBM Corporation
# Author: Naveed AUS <naveedaus@in.ibm.com>

"""
NVMe over Fabrics (NVMe-oF) TCP Target Configuration and Testing.
This test suite configures an NVMe-TCP target, creates subsystems,
namespaces, and validates the target configuration.
"""

import os
from avocado import Test
from avocado.utils import process
from avocado.utils.software_manager.manager import SoftwareManager


class NVMeTCPTargetTest(Test):
    """
    NVMe-oF TCP Target configuration and validation test suite.
    
    :param backend_device: Block device to export (e.g., /dev/nvme0n1)
    :param target_ip: IP address for NVMe-TCP target
    :param target_port: Port number for NVMe-TCP service (default: 4420)
    :param subsystem_nqn: NVMe Qualified Name for subsystem
    :param namespace_count: Number of namespaces to create
    """

    def setUp(self):
        """
        Setup NVMe-TCP target environment and validate prerequisites.
        """
        self.backend_device = self.params.get('backend_device', default='/dev/nvme0n1')
        self.target_ip = self.params.get('target_ip', default='192.168.100.10')
        self.target_port = self.params.get('target_port', default='4420')
        self.subsystem_nqn = self.params.get('subsystem_nqn', 
                                            default='nqn.2026-01.lab:nvme:target1')
        self.namespace_count = self.params.get('namespace_count', default=1)
        self.port_id = self.params.get('port_id', default='1')
        
        # Validate backend device exists
        if not os.path.exists(self.backend_device):
            self.cancel(f"Backend device {self.backend_device} does not exist")
        
        # Install required packages
        smm = SoftwareManager()
        if not smm.check_installed("nvme-cli"):
            if not smm.install("nvme-cli"):
                self.cancel("Failed to install nvme-cli")
        
        self.log.info("NVMe-TCP Target Test Setup Complete")
        self.log.info(f"Backend Device: {self.backend_device}")
        self.log.info(f"Target IP: {self.target_ip}")
        self.log.info(f"Subsystem NQN: {self.subsystem_nqn}")

    def load_kernel_modules(self):
        """
        Load required kernel modules for NVMe-TCP target.
        """
        modules = ['nvmet', 'nvmet-tcp']
        for module in modules:
            cmd = f"modprobe {module}"
            result = process.run(cmd, shell=True, ignore_status=True)
            if result.exit_status != 0:
                self.fail(f"Failed to load kernel module: {module}")
        
        # Verify modules are loaded
        cmd = "lsmod | grep nvmet"
        output = process.system_output(cmd, shell=True).decode('utf-8')
        if 'nvmet' not in output or 'nvmet_tcp' not in output:
            self.fail("NVMe target modules not loaded properly")
        
        self.log.info("Kernel modules loaded successfully")

    def mount_configfs(self):
        """
        Ensure configfs is mounted.
        """
        cmd = "mount | grep configfs || mount -t configfs none /sys/kernel/config"
        process.run(cmd, shell=True, ignore_status=True)
        self.log.info("Configfs mounted")

    def create_subsystem(self):
        """
        Create NVMe subsystem with specified NQN.
        """
        subsys_path = f"/sys/kernel/config/nvmet/subsystems/{self.subsystem_nqn}"
        
        # Create subsystem directory
        if not os.path.exists(subsys_path):
            os.makedirs(subsys_path)
            self.log.info(f"Created subsystem: {self.subsystem_nqn}")
        
        # Allow any host (for lab/test environment)
        cmd = f"echo 1 > {subsys_path}/attr_allow_any_host"
        result = process.run(cmd, shell=True, ignore_status=True)
        if result.exit_status != 0:
            self.fail("Failed to set attr_allow_any_host")
        
        self.log.info("Subsystem created and configured")

    def create_namespaces(self):
        """
        Create and enable namespaces on the subsystem.
        """
        subsys_path = f"/sys/kernel/config/nvmet/subsystems/{self.subsystem_nqn}"
        
        for ns_id in range(1, self.namespace_count + 1):
            ns_path = f"{subsys_path}/namespaces/{ns_id}"
            
            # Create namespace directory
            if not os.path.exists(ns_path):
                os.makedirs(ns_path)
            
            # Set device path
            device_path = self.backend_device
            if self.namespace_count > 1:
                # For multiple namespaces, append namespace number
                device_path = f"{self.backend_device.rstrip('1')}{ns_id}"
            
            cmd = f"echo -n {device_path} > {ns_path}/device_path"
            result = process.run(cmd, shell=True, ignore_status=True)
            if result.exit_status != 0:
                self.log.warn(f"Failed to set device_path for namespace {ns_id}")
                continue
            
            # Enable namespace
            cmd = f"echo 1 > {ns_path}/enable"
            result = process.run(cmd, shell=True, ignore_status=True)
            if result.exit_status != 0:
                self.fail(f"Failed to enable namespace {ns_id}")
            
            self.log.info(f"Namespace {ns_id} created and enabled")

    def configure_port(self):
        """
        Configure NVMe-TCP port with transport parameters.
        """
        port_path = f"/sys/kernel/config/nvmet/ports/{self.port_id}"
        
        # Create port directory
        if not os.path.exists(port_path):
            os.makedirs(port_path)
        
        # Set transport parameters
        params = {
            'addr_trtype': 'tcp',
            'addr_adrfam': 'ipv4',
            'addr_traddr': self.target_ip,
            'addr_trsvcid': self.target_port
        }
        
        for param, value in params.items():
            cmd = f"echo {value} > {port_path}/{param}"
            result = process.run(cmd, shell=True, ignore_status=True)
            if result.exit_status != 0:
                self.fail(f"Failed to set {param} to {value}")
        
        self.log.info(f"Port {self.port_id} configured: {self.target_ip}:{self.target_port}")

    def bind_subsystem_to_port(self):
        """
        Bind the subsystem to the configured port.
        """
        port_path = f"/sys/kernel/config/nvmet/ports/{self.port_id}"
        subsys_path = f"/sys/kernel/config/nvmet/subsystems/{self.subsystem_nqn}"
        link_path = f"{port_path}/subsystems/{self.subsystem_nqn}"
        
        # Create symbolic link
        if not os.path.exists(link_path):
            os.symlink(subsys_path, link_path)
            self.log.info(f"Subsystem bound to port {self.port_id}")
        else:
            self.log.info("Subsystem already bound to port")

    def verify_target_configuration(self):
        """
        Verify the NVMe-TCP target is properly configured.
        """
        # Check if nvmetcli is available
        cmd = "which nvmetcli"
        result = process.run(cmd, shell=True, ignore_status=True)
        
        if result.exit_status == 0:
            # Use nvmetcli to list configuration
            cmd = "nvmetcli ls"
            output = process.system_output(cmd, shell=True, ignore_status=True).decode('utf-8')
            self.log.info("NVMe Target Configuration:")
            self.log.info(output)
            
            if self.subsystem_nqn not in output:
                self.fail("Subsystem not found in nvmetcli output")
        else:
            # Manual verification
            subsys_path = f"/sys/kernel/config/nvmet/subsystems/{self.subsystem_nqn}"
            port_path = f"/sys/kernel/config/nvmet/ports/{self.port_id}"
            
            if not os.path.exists(subsys_path):
                self.fail("Subsystem path does not exist")
            
            if not os.path.exists(port_path):
                self.fail("Port path does not exist")
        
        # Check dmesg for nvmet_tcp messages
        cmd = "dmesg | grep nvmet_tcp | tail -10"
        output = process.system_output(cmd, shell=True, ignore_status=True).decode('utf-8')
        self.log.info("Recent nvmet_tcp kernel messages:")
        self.log.info(output)

    def configure_firewall(self):
        """
        Configure firewall to allow NVMe-TCP traffic.
        """
        # Check if firewalld is running
        cmd = "systemctl is-active firewalld"
        result = process.run(cmd, shell=True, ignore_status=True)
        
        if result.exit_status == 0:
            # Firewalld is active, add port
            cmd = f"firewall-cmd --add-port={self.target_port}/tcp --permanent"
            process.run(cmd, shell=True, ignore_status=True)
            cmd = "firewall-cmd --reload"
            process.run(cmd, shell=True, ignore_status=True)
            self.log.info(f"Firewall configured for port {self.target_port}")
        else:
            self.log.info("Firewalld not active, skipping firewall configuration")

    def test_load_modules(self):
        """
        Test: Load NVMe target kernel modules.
        """
        self.load_kernel_modules()

    def test_full_target_setup(self):
        """
        Test: Complete NVMe-TCP target setup and configuration.
        """
        self.load_kernel_modules()
        self.mount_configfs()
        self.create_subsystem()
        self.create_namespaces()
        self.configure_port()
        self.bind_subsystem_to_port()
        self.configure_firewall()
        self.verify_target_configuration()
        self.log.info("NVMe-TCP Target setup completed successfully")

    def test_verify_only(self):
        """
        Test: Verify existing NVMe-TCP target configuration.
        """
        self.verify_target_configuration()

    def cleanup_target(self):
        """
        Cleanup NVMe-TCP target configuration.
        """
        try:
            # Unbind subsystem from port
            link_path = f"/sys/kernel/config/nvmet/ports/{self.port_id}/subsystems/{self.subsystem_nqn}"
            if os.path.exists(link_path):
                os.unlink(link_path)
            
            # Disable and remove namespaces
            subsys_path = f"/sys/kernel/config/nvmet/subsystems/{self.subsystem_nqn}"
            for ns_id in range(1, self.namespace_count + 1):
                ns_path = f"{subsys_path}/namespaces/{ns_id}"
                if os.path.exists(ns_path):
                    # Disable namespace
                    cmd = f"echo 0 > {ns_path}/enable"
                    process.run(cmd, shell=True, ignore_status=True)
                    # Remove namespace directory
                    os.rmdir(ns_path)
            
            # Remove subsystem
            if os.path.exists(subsys_path):
                os.rmdir(subsys_path)
            
            # Remove port
            port_path = f"/sys/kernel/config/nvmet/ports/{self.port_id}"
            if os.path.exists(port_path):
                os.rmdir(port_path)
            
            self.log.info("Target cleanup completed")
        except Exception as e:
            self.log.warn(f"Cleanup error: {str(e)}")

    def tearDown(self):
        """
        Cleanup after test execution.
        """
        cleanup_on_teardown = self.params.get('cleanup_on_teardown', default=False)
        if cleanup_on_teardown:
            self.cleanup_target()
# Assisted with AI tools
