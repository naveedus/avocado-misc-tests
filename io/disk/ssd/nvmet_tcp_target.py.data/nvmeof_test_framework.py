#!/usr/bin/env python3
"""
NVMe-oF Remote Testing Framework

Copyright 2026 Naveed AUS, IBM Corporation
Author: Naveed AUS <naveedaus@in.ibm.com>
Assisted with AI tools

This framework provides a Python-based automation system for testing NVMe-oF
TCP targets across remote systems.
"""

import paramiko
import json
import time
import sys
from typing import Dict, List, Optional
from dataclasses import dataclass
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class SSHConfig:
    """SSH connection configuration"""
    host: str
    username: str
    password: str
    port: int = 22


@dataclass
class TargetConfig:
    """NVMe-oF target configuration"""
    ssh: SSHConfig
    data_ip: str
    subsys_nqn: str
    port: int = 4420
    backend_device: str = '/dev/nvme0n1'


@dataclass
class InitiatorConfig:
    """NVMe-oF initiator configuration"""
    ssh: SSHConfig


class SSHManager:
    """Manages SSH connections and command execution"""
    
    def __init__(self, config: SSHConfig):
        self.config = config
        self.client = None
        
    def connect(self):
        """Establish SSH connection"""
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.client.connect(
                hostname=self.config.host,
                username=self.config.username,
                password=self.config.password,
                port=self.config.port
            )
            logger.info(f"Connected to {self.config.host}")
        except Exception as e:
            logger.error(f"Failed to connect to {self.config.host}: {e}")
            raise
    
    def execute(self, command: str, timeout: int = 300) -> Dict:
        """Execute command and return result"""
        if not self.client:
            raise RuntimeError("Not connected. Call connect() first.")
        
        try:
            stdin, stdout, stderr = self.client.exec_command(command, timeout=timeout)
            exit_code = stdout.channel.recv_exit_status()
            
            return {
                'stdout': stdout.read().decode('utf-8', errors='replace'),
                'stderr': stderr.read().decode('utf-8', errors='replace'),
                'exit_code': exit_code,
                'success': exit_code == 0
            }
        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            return {
                'stdout': '',
                'stderr': str(e),
                'exit_code': -1,
                'success': False
            }
    
    def close(self):
        """Close SSH connection"""
        if self.client:
            self.client.close()
            logger.info(f"Disconnected from {self.config.host}")


class NVMeOFTarget:
    """Manages NVMe-oF target operations"""
    
    def __init__(self, config: TargetConfig):
        self.config = config
        self.ssh = SSHManager(config.ssh)
        
    def setup(self) -> bool:
        """Setup NVMe-oF target using Avocado test"""
        logger.info("Setting up NVMe-oF target...")
        
        self.ssh.connect()
        
        cmd = """
        cd /home/avocado-fvt-wrapper/tests/avocado-misc-tests/io/disk/ssd
        avocado run --max-parallel-tasks=1 \
            nvmet_tcp_target.py:NVMeTCPTargetTest.test_full_target_setup \
            -m nvmet_tcp_target.py.data/nvmet_tcp_target.yaml \
            --mux-filter-only /TestScenarios/single_namespace
        """
        
        result = self.ssh.execute(cmd, timeout=120)
        
        if result['success']:
            logger.info("Target setup completed successfully")
            return True
        else:
            logger.error(f"Target setup failed: {result['stderr']}")
            return False
    
    def verify(self) -> bool:
        """Verify target is properly configured"""
        logger.info("Verifying target configuration...")
        
        checks = [
            ("Module loaded", "lsmod | grep -q nvmet"),
            ("Subsystem exists", f"[ -d /sys/kernel/config/nvmet/subsystems/{self.config.subsys_nqn} ]"),
            ("Port configured", "[ -d /sys/kernel/config/nvmet/ports/1 ]")
        ]
        
        for check_name, check_cmd in checks:
            result = self.ssh.execute(check_cmd)
            if not result['success']:
                logger.error(f"Verification failed: {check_name}")
                return False
            logger.info(f"✓ {check_name}")
        
        logger.info("Target verification passed")
        return True
    
    def cleanup(self):
        """Cleanup target configuration"""
        logger.info("Cleaning up target configuration...")
        
        cleanup_script = """
        for link in /sys/kernel/config/nvmet/ports/*/subsystems/*; do
            [ -L "$link" ] && unlink "$link" 2>/dev/null
        done
        
        for ns in /sys/kernel/config/nvmet/subsystems/*/namespaces/*; do
            if [ -d "$ns" ]; then
                echo 0 > "$ns/enable" 2>/dev/null || true
                rmdir "$ns" 2>/dev/null || true
            fi
        done
        
        for subsys in /sys/kernel/config/nvmet/subsystems/*; do
            [ -d "$subsys" ] && rmdir "$subsys" 2>/dev/null || true
        done
        
        for port in /sys/kernel/config/nvmet/ports/*; do
            [ -d "$port" ] && rmdir "$port" 2>/dev/null || true
        done
        """
        
        result = self.ssh.execute(cleanup_script)
        if result['success']:
            logger.info("Cleanup completed")
        else:
            logger.warning(f"Cleanup had issues: {result['stderr']}")
        
        self.ssh.close()


class NVMeOFInitiator:
    """Manages NVMe-oF initiator operations"""
    
    def __init__(self, config: InitiatorConfig, target_config: TargetConfig):
        self.config = config
        self.target_config = target_config
        self.ssh = SSHManager(config.ssh)
        self.device = None
        
    def discover(self) -> bool:
        """Discover NVMe-oF targets"""
        logger.info("Discovering NVMe-oF targets...")
        
        self.ssh.connect()
        
        cmd = f"nvme discover -t tcp -a {self.target_config.data_ip} -s {self.target_config.port}"
        result = self.ssh.execute(cmd)
        
        if result['success'] and self.target_config.subsys_nqn in result['stdout']:
            logger.info(f"✓ Target discovered: {self.target_config.subsys_nqn}")
            return True
        else:
            logger.error("Target discovery failed")
            return False
    
    def connect(self) -> bool:
        """Connect to NVMe-oF target"""
        logger.info("Connecting to target...")
        
        cmd = f"nvme connect -t tcp -n {self.target_config.subsys_nqn} -a {self.target_config.data_ip} -s {self.target_config.port}"
        result = self.ssh.execute(cmd)
        
        if not result['success']:
            logger.error(f"Connection failed: {result['stderr']}")
            return False
        
        # Wait for device to appear
        time.sleep(2)
        
        # Find the connected device
        result = self.ssh.execute("nvme list | grep tcp | head -1 | awk '{print $1}'")
        if result['success'] and result['stdout'].strip():
            self.device = result['stdout'].strip()
            logger.info(f"✓ Connected to device: {self.device}")
            return True
        else:
            logger.error("Failed to find connected device")
            return False
    
    def run_fio_test(self, test_name: str, rw: str, bs: str, 
                     size: Optional[str] = None, runtime: Optional[int] = None) -> Dict:
        """Run FIO test on connected device"""
        if not self.device:
            raise RuntimeError("No device connected")
        
        logger.info(f"Running FIO test: {test_name} ({rw}, {bs})")
        
        # Build FIO command
        cmd_parts = [
            f"fio --name={test_name}",
            f"--filename={self.device}",
            f"--rw={rw}",
            f"--bs={bs}",
            "--direct=1",
            "--output-format=json"
        ]
        
        if size:
            cmd_parts.append(f"--size={size}")
        if runtime:
            cmd_parts.append(f"--runtime={runtime}")
        
        cmd = " ".join(cmd_parts)
        result = self.ssh.execute(cmd, timeout=runtime + 60 if runtime else 300)
        
        if result['success']:
            try:
                data = json.loads(result['stdout'])
                logger.info(f"✓ Test {test_name} completed")
                return data
            except json.JSONDecodeError:
                logger.error(f"Failed to parse FIO output for {test_name}")
                return {}
        else:
            logger.error(f"FIO test {test_name} failed: {result['stderr']}")
            return {}
    
    def disconnect(self):
        """Disconnect from target"""
        logger.info("Disconnecting from target...")
        
        cmd = f"nvme disconnect -n {self.target_config.subsys_nqn}"
        result = self.ssh.execute(cmd)
        
        if result['success']:
            logger.info("✓ Disconnected")
        else:
            logger.warning(f"Disconnect had issues: {result['stderr']}")
        
        self.ssh.close()


class TestOrchestrator:
    """Orchestrates complete test execution"""
    
    def __init__(self, target_config: TargetConfig, initiator_config: InitiatorConfig):
        self.target = NVMeOFTarget(target_config)
        self.initiator = NVMeOFInitiator(initiator_config, target_config)
        self.results = {}
        
    def run_test_suite(self) -> Dict:
        """Run complete test suite"""
        logger.info("=" * 60)
        logger.info("Starting NVMe-oF Remote Test Suite")
        logger.info("=" * 60)
        
        try:
            # Phase 1: Setup target
            logger.info("\n[Phase 1] Setting up target...")
            if not self.target.setup():
                raise RuntimeError("Target setup failed")
            
            # Phase 2: Verify target
            logger.info("\n[Phase 2] Verifying target...")
            if not self.target.verify():
                raise RuntimeError("Target verification failed")
            
            # Phase 3: Discover target
            logger.info("\n[Phase 3] Discovering target from initiator...")
            if not self.initiator.discover():
                raise RuntimeError("Target discovery failed")
            
            # Phase 4: Connect to target
            logger.info("\n[Phase 4] Connecting to target...")
            if not self.initiator.connect():
                raise RuntimeError("Connection failed")
            
            # Phase 5: Run I/O tests
            logger.info("\n[Phase 5] Running I/O tests...")
            
            tests = [
                ("seq_read", "read", "1M", "1G", None),
                ("rand_read", "randread", "4k", None, 60),
                ("rand_write", "randwrite", "4k", None, 60),
                ("randrw", "randrw", "4k", None, 60)
            ]
            
            for test_name, rw, bs, size, runtime in tests:
                result = self.initiator.run_fio_test(test_name, rw, bs, size, runtime)
                if result:
                    self.results[test_name] = result
            
            # Phase 6: Disconnect
            logger.info("\n[Phase 6] Disconnecting...")
            self.initiator.disconnect()
            
            # Phase 7: Display results
            logger.info("\n[Phase 7] Test Results Summary")
            self._display_results()
            
        except Exception as e:
            logger.error(f"Test suite failed: {e}")
            self.results['error'] = str(e)
        
        finally:
            # Cleanup
            logger.info("\n[Cleanup] Cleaning up target...")
            self.target.cleanup()
        
        logger.info("\n" + "=" * 60)
        logger.info("Test Suite Completed")
        logger.info("=" * 60)
        
        return self.results
    
    def _display_results(self):
        """Display test results summary"""
        for test_name, data in self.results.items():
            if 'jobs' in data:
                for job in data['jobs']:
                    print(f"\n{job['jobname']}:")
                    if 'read' in job and job['read']['io_bytes'] > 0:
                        bw_mb = job['read']['bw'] / 1024
                        iops = job['read']['iops']
                        print(f"  Read:  {bw_mb:.2f} MB/s, {iops:.0f} IOPS")
                    if 'write' in job and job['write']['io_bytes'] > 0:
                        bw_mb = job['write']['bw'] / 1024
                        iops = job['write']['iops']
                        print(f"  Write: {bw_mb:.2f} MB/s, {iops:.0f} IOPS")


def main():
    """Main entry point"""
    # Configuration
    target_config = TargetConfig(
        ssh=SSHConfig(
            host='10.48.35.49',
            username='root',
            password='llm@fvt'
        ),
        data_ip='192.168.1.49',
        subsys_nqn='nqn.2026-01.lab:nvme:target1',
        port=4420
    )
    
    initiator_config = InitiatorConfig(
        ssh=SSHConfig(
            host='10.48.35.50',  # Change to actual initiator IP
            username='root',
            password='password'  # Change to actual password
        )
    )
    
    # Run tests
    orchestrator = TestOrchestrator(target_config, initiator_config)
    results = orchestrator.run_test_suite()
    
    # Save results to file
    with open('nvmeof_test_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    logger.info("\nResults saved to: nvmeof_test_results.json")
    
    return 0 if 'error' not in results else 1


if __name__ == '__main__':
    sys.exit(main())
