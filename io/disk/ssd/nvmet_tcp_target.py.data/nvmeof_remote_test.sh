#!/bin/bash
# nvmeof_remote_test.sh - NVMe-oF Remote Testing Automation Script
#
# Copyright 2026 Naveed AUS, IBM Corporation
# Author: Naveed AUS <naveedaus@in.ibm.com>
# Assisted with AI tools
#
# This script orchestrates NVMe-oF TCP target testing across remote systems.
# It sets up the target on one system and runs initiator tests on another.

set -e

# Configuration
TARGET_IP="${TARGET_IP:-10.48.35.49}"
TARGET_DATA_IP="${TARGET_DATA_IP:-192.168.1.49}"
INITIATOR_IP="${INITIATOR_IP:-10.48.35.50}"
SUBSYS_NQN="${SUBSYS_NQN:-nqn.2026-01.lab:nvme:target1}"
TARGET_PORT="${TARGET_PORT:-4420}"
TEST_SCENARIO="${TEST_SCENARIO:-single_namespace}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# Function to setup NVMe-oF target
setup_target() {
    log_info "Setting up NVMe-oF target on $TARGET_IP..."
    
    ssh root@$TARGET_IP << 'EOF'
        cd /home/avocado-fvt-wrapper/tests/avocado-misc-tests/io/disk/ssd
        avocado run --max-parallel-tasks=1 \
            nvmet_tcp_target.py:NVMeTCPTargetTest.test_full_target_setup \
            -m nvmet_tcp_target.py.data/nvmet_tcp_target.yaml \
            --mux-filter-only /TestScenarios/single_namespace
EOF
    
    if [ $? -eq 0 ]; then
        log_info "Target setup completed successfully"
        return 0
    else
        log_error "Target setup failed"
        return 1
    fi
}

# Function to verify target is ready
verify_target() {
    log_info "Verifying target is ready..."
    
    ssh root@$TARGET_IP << EOF
        # Check if modules are loaded
        if ! lsmod | grep -q nvmet; then
            echo "ERROR: nvmet module not loaded"
            exit 1
        fi
        
        # Check if subsystem exists
        if [ ! -d /sys/kernel/config/nvmet/subsystems/$SUBSYS_NQN ]; then
            echo "ERROR: Subsystem $SUBSYS_NQN not found"
            exit 1
        fi
        
        # Check if port is configured
        if [ ! -d /sys/kernel/config/nvmet/ports/1 ]; then
            echo "ERROR: Port 1 not configured"
            exit 1
        fi
        
        echo "Target verification passed"
EOF
    
    return $?
}

# Function to run initiator tests
run_initiator_tests() {
    log_info "Running initiator tests on $INITIATOR_IP..."
    
    ssh root@$INITIATOR_IP << EOF
        set -e
        
        # Discovery
        echo "=== Discovery Phase ==="
        nvme discover -t tcp -a $TARGET_DATA_IP -s $TARGET_PORT
        
        # Connect
        echo ""
        echo "=== Connection Phase ==="
        nvme connect -t tcp -n $SUBSYS_NQN -a $TARGET_DATA_IP -s $TARGET_PORT
        sleep 2
        
        # Find device
        NVME_DEV=\$(nvme list | grep tcp | head -1 | awk '{print \$1}')
        if [ -z "\$NVME_DEV" ]; then
            echo "ERROR: No NVMe-oF device found"
            exit 1
        fi
        echo "Connected device: \$NVME_DEV"
        
        # Create test directory
        mkdir -p /tmp/nvmeof_test_results
        cd /tmp/nvmeof_test_results
        
        # I/O Tests
        echo ""
        echo "=== I/O Testing Phase ==="
        
        echo "Running sequential read test (1MB blocks, 1GB)..."
        fio --name=seq_read --filename=\$NVME_DEV --rw=read --bs=1M \
            --size=1G --direct=1 --output-format=json > seq_read.json
        
        echo "Running random read test (4K blocks, 60s)..."
        fio --name=rand_read --filename=\$NVME_DEV --rw=randread --bs=4k \
            --runtime=60 --direct=1 --output-format=json > rand_read.json
        
        echo "Running random write test (4K blocks, 60s)..."
        fio --name=rand_write --filename=\$NVME_DEV --rw=randwrite --bs=4k \
            --runtime=60 --direct=1 --output-format=json > rand_write.json
        
        echo "Running mixed read/write test (4K blocks, 60s)..."
        fio --name=randrw --filename=\$NVME_DEV --rw=randrw --bs=4k \
            --runtime=60 --direct=1 --rwmixread=70 --output-format=json > randrw.json
        
        # Disconnect
        echo ""
        echo "=== Disconnection Phase ==="
        nvme disconnect -n $SUBSYS_NQN
        
        # Display results summary
        echo ""
        echo "=== Test Results Summary ==="
        for file in seq_read.json rand_read.json rand_write.json randrw.json; do
            if [ -f "\$file" ]; then
                echo "Results from \$file:"
                python3 -c "
import json
with open('\$file') as f:
    data = json.load(f)
    for job in data['jobs']:
        print(f\"  Job: {job['jobname']}\")
        if 'read' in job and job['read']['io_bytes'] > 0:
            print(f\"    Read BW: {job['read']['bw']/1024:.2f} MB/s, IOPS: {job['read']['iops']:.0f}\")
        if 'write' in job and job['write']['io_bytes'] > 0:
            print(f\"    Write BW: {job['write']['bw']/1024:.2f} MB/s, IOPS: {job['write']['iops']:.0f}\")
"
            fi
        done
        
        echo ""
        echo "Full results saved in: /tmp/nvmeof_test_results/"
EOF
    
    return $?
}

# Function to cleanup target
cleanup_target() {
    log_info "Cleaning up target configuration..."
    
    ssh root@$TARGET_IP << 'EOF'
        # Cleanup script
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
        
        echo "Cleanup completed"
EOF
    
    return $?
}

# Function to collect logs
collect_logs() {
    log_info "Collecting logs from both systems..."
    
    mkdir -p ./test_logs
    
    # Target logs
    ssh root@$TARGET_IP "dmesg | tail -100" > ./test_logs/target_dmesg.log
    
    # Initiator logs
    ssh root@$INITIATOR_IP "dmesg | tail -100" > ./test_logs/initiator_dmesg.log
    
    log_info "Logs saved to ./test_logs/"
}

# Main execution
main() {
    echo "=========================================="
    echo "  NVMe-oF Remote Testing Automation"
    echo "=========================================="
    echo ""
    echo "Configuration:"
    echo "  Target IP:      $TARGET_IP"
    echo "  Target Data IP: $TARGET_DATA_IP"
    echo "  Initiator IP:   $INITIATOR_IP"
    echo "  Subsystem NQN:  $SUBSYS_NQN"
    echo "  Port:           $TARGET_PORT"
    echo "  Test Scenario:  $TEST_SCENARIO"
    echo ""
    
    # Step 1: Setup target
    echo "Step 1: Setting up target..."
    if ! setup_target; then
        log_error "Target setup failed. Aborting."
        exit 1
    fi
    
    # Step 2: Verify target
    echo ""
    echo "Step 2: Verifying target..."
    if ! verify_target; then
        log_error "Target verification failed. Cleaning up..."
        cleanup_target
        exit 1
    fi
    
    # Step 3: Run initiator tests
    echo ""
    echo "Step 3: Running initiator tests..."
    if ! run_initiator_tests; then
        log_error "Initiator tests failed. Cleaning up..."
        cleanup_target
        collect_logs
        exit 1
    fi
    
    # Step 4: Cleanup
    echo ""
    echo "Step 4: Cleaning up..."
    cleanup_target
    
    # Step 5: Collect logs
    echo ""
    echo "Step 5: Collecting logs..."
    collect_logs
    
    echo ""
    echo "=========================================="
    log_info "All tests completed successfully!"
    echo "=========================================="
}

# Handle script arguments
case "${1:-}" in
    setup)
        setup_target
        ;;
    verify)
        verify_target
        ;;
    test)
        run_initiator_tests
        ;;
    cleanup)
        cleanup_target
        ;;
    logs)
        collect_logs
        ;;
    *)
        main
        ;;
esac
