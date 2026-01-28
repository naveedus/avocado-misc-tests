# IOMMUFD PPC64 Test - Code Changes Explanation

## Overview
This document explains the kernel patch for IOMMUFD (I/O Memory Management Unit File Descriptor) support on PowerPC 64-bit architecture and the corresponding test cases.

## Kernel Patch Summary

### What is IOMMUFD?
IOMMUFD is a modern Linux kernel interface for managing IOMMU operations, replacing the older VFIO Type1 interface. It provides better support for device passthrough to virtual machines and containers.

### Problem Being Solved
On PPC64 systems, IOVA (I/O Virtual Address) ranges depend on DMA window types and properties. The existing VFIO Type1 driver doesn't expose the attributes of non-default 64-bit DMA windows, which limits flexibility in configuring DMA operations.

## Key Code Changes Explained

### 1. **arch/powerpc/include/asm/iommu.h** (2 lines changed)
```c
- unsigned long attrs);
+ unsigned long attrs, bool is_phys);
```
**Explanation:** Added `is_phys` parameter to distinguish between physical and virtual address mappings in IOMMU operations.

### 2. **arch/powerpc/kernel/iommu.c** (181 lines added)
This is the core implementation file with several new functions:

#### a) **New Structure: `ppc64_domain`**
```c
+struct ppc64_domain {
+    struct iommu_domain  domain;
+    struct device        *device;
+    struct iommu_table   *table;
+    spinlock_t           list_lock;
+    struct rcu_head      rcu;
+};
```
**Explanation:** Container structure that links IOMMU domain with PowerPC-specific IOMMU table and device information. Uses RCU (Read-Copy-Update) for safe concurrent access.

#### b) **spapr_tce_domain_alloc_paging()**
```c
+static struct iommu_domain *spapr_tce_domain_alloc_paging(struct device *dev)
+{
+    struct iommu_group *grp = iommu_group_get(dev);
+    struct iommu_table_group *table_group;
+    struct ppc64_domain *ppc64_domain;
+    struct iommu_table *ptbl;
+    
+    // Allocate domain structure
+    ppc64_domain = kzalloc(sizeof(*ppc64_domain), GFP_KERNEL);
+    
+    // Create default 1GB DMA window
+    ret = table_group->ops->create_table(table_group, 0, 0xc, 0x40000000, 1, &ptbl);
+    
+    // Configure domain properties
+    ppc64_domain->domain.pgsize_bitmap = SZ_4K;
+    ppc64_domain->domain.geometry.force_aperture = true;
+    ppc64_domain->domain.geometry.aperture_start = 0;
+    ppc64_domain->domain.geometry.aperture_end = 0x40000000; // 1GB
+    
+    return &ppc64_domain->domain;
+}
```
**Explanation:** 
- Allocates a new IOMMU paging domain for device passthrough
- Creates a default 1GB DMA window (0x40000000 = 1GB)
- Sets page size to 4KB (SZ_4K)
- Configures aperture (valid IOVA range) from 0 to 1GB
- This is the "default window hardcode" mentioned in the patch

#### c) **spapr_tce_iommu_unmap_pages()**
```c
+static size_t spapr_tce_iommu_unmap_pages(struct iommu_domain *domain,
+                                          unsigned long iova,
+                                          size_t pgsize, size_t pgcount,
+                                          struct iommu_iotlb_gather *gather)
+{
+    struct ppc64_domain *ppc64_domain = to_ppc64_domain(domain);
+    // Unmap pages from IOMMU table
+}
```
**Explanation:** Handles unmapping of IOVA pages when device is detached or memory is freed.

### 3. **IOMMU_PAGE_MASK Changes**
```c
// Old code:
- IOMMU_PAGE_MASK(tbl), direction, attrs);

// New code:
+ IOMMU_PAGE_MASK(tbl), direction, attrs, false);
```
**Explanation:** 
- Added `false` parameter for `is_phys` flag
- `false` indicates virtual address mapping (not physical)
- This change appears in multiple files to maintain API consistency

### 4. **Domain Ownership Transfer**
```c
+    if (old && old->type == IOMMU_DOMAIN_DMA) {
+        ret = table_group->ops->unset_window(table_group, 0);
+        if (ret)
+            goto exit;
+    }
+    
+    ret = table_group->ops->take_ownership(table_group, dev);
```
**Explanation:**
- Before assigning device to new domain, releases it from old domain
- Unsets existing DMA window configuration
- Takes ownership for the new domain
- Ensures clean state transitions

## Architecture-Specific Details

### SPAPR TCE (Translation Control Entry)
- PowerPC uses TCE tables for IOMMU translations
- TCE is similar to page table entries but for I/O devices
- Each TCE maps an IOVA to a physical address

### DMA Windows
- **Default Window**: 1GB (0x0 - 0x40000000)
- **64-bit Windows**: Can be larger (4GB or 512PiB) but not yet supported in this patch
- Window size determines maximum DMA-able memory range

### Platform Differences
- **PowerNV (bare metal)**: Direct hardware access, uses OPAL firmware
- **pSeries (LPAR)**: Virtualized, uses hypervisor calls

## Test Cases Explanation

### Test 1: `test_iommu_groups_exist()`
**Purpose:** Verify IOMMU infrastructure is initialized
**What it tests:** Checks `/sys/kernel/iommu_groups/` exists and contains groups

### Test 2: `test_default_dma_window()`
**Purpose:** Verify the 1GB default DMA window is configured
**What it tests:** Validates devices are assigned to IOMMU groups with proper DMA windows

### Test 3: `test_iommu_domain_allocation()`
**Purpose:** Test the new `spapr_tce_domain_alloc_paging()` function
**What it tests:** Checks dmesg for successful IOMMU domain allocation

### Test 4: `test_iommu_page_mapping()`
**Purpose:** Verify IOMMU page mapping with new `is_phys` parameter
**What it tests:** Checks reserved regions and page size configuration

### Test 5: `test_single_device_passthrough()`
**Purpose:** Test device assignment to IOMMU domain
**What it tests:** 
- Device exists in sysfs
- Device is in an IOMMU group
- Device can be bound/unbound from drivers

### Test 6: `test_iommu_table_operations()`
**Purpose:** Verify TCE table get/put operations
**What it tests:** Checks IOMMU debugfs for table information

### Test 7: `test_dma_window_attributes()`
**Purpose:** Validate DMA window configuration matches patch
**What it tests:**
- Page size = 4KB
- Aperture start = 0
- Aperture end = 1GB (0x40000000)
- Force aperture = true

### Test 8: `test_iommu_unmap_operations()`
**Purpose:** Test `spapr_tce_iommu_unmap_pages()` function
**What it tests:** Checks for IOMMU errors in dmesg during unmap

### Test 9: `test_powerpc_specific_features()`
**Purpose:** Verify PowerPC-specific IOMMU features
**What it tests:**
- Platform detection (PowerNV vs pSeries)
- SPAPR TCE support in kernel

### Test 10: `test_iommu_group_devices()`
**Purpose:** Comprehensive device-to-group mapping test
**What it tests:**
- All devices are in IOMMU groups
- Device vendor/device IDs are readable
- Group membership is correct

## Running the Tests

### Basic test (no device passthrough):
```bash
avocado run avocado-misc-tests/io/pci/iommufd_ppc64_test.py \
    -m avocado-misc-tests/io/pci/iommufd_ppc64_test.py.data/iommufd_ppc64_test.yaml:basic
```

### Single device passthrough test:
```bash
# First, identify your PCI device
lspci -nn

# Edit the YAML file to set the correct pci_device address
# Then run:
avocado run avocado-misc-tests/io/pci/iommufd_ppc64_test.py \
    -m avocado-misc-tests/io/pci/iommufd_ppc64_test.py.data/iommufd_ppc64_test.yaml:single_device
```

### Platform-specific tests:
```bash
# For PowerNV (bare metal)
avocado run avocado-misc-tests/io/pci/iommufd_ppc64_test.py \
    -m avocado-misc-tests/io/pci/iommufd_ppc64_test.py.data/iommufd_ppc64_test.yaml:powernv

# For pSeries (LPAR)
avocado run avocado-misc-tests/io/pci/iommufd_ppc64_test.py \
    -m avocado-misc-tests/io/pci/iommufd_ppc64_test.py.data/iommufd_ppc64_test.yaml:pseries
```

## Known Limitations (from patch)

1. **Single device only**: Multi-device support not yet implemented
2. **Default window only**: Only 1GB DMA window exposed (no 64-bit window support)
3. **No KVM support**: Cannot yet use with KVM virtual machines
4. **No EEH support**: Enhanced Error Handling not implemented
5. **No vfio-compat**: Needs separate "vfio-spapr-compat" driver
6. **No multifunction**: Multiple devices in same IOMMU group not supported
7. **No hotplug**: Device plug/unplug not fully tested

## Future Work

- Second DMA window support (larger than 1GB)
- KVM integration for VM device passthrough
- EEH (Enhanced Error Handling) support
- Multiple device support in same IOMMU group
- SRIOV VF (Virtual Function) assignment
- Race condition fixes for hotplug scenarios
- Comprehensive self-tests

## References

- Patch: https://lore.kernel.org/lkml/176953894915.725.1102545144304639827.stgit@linux.ibm.com/
- QEMU WIP: https://github.com/shivaprasadbhat/qemu/tree/iommufd-wip
- Linux IOMMU subsystem: Documentation/driver-api/iommu.rst
- PowerPC IOMMU: arch/powerpc/kernel/iommu.c