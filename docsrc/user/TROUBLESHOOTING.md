# Troubleshooting Guide

This guide provides solutions for common connectivity and protocol issues encountered when using the `hostlink` Python library.

---

## Connection Issues

### `HostLinkConnectionError: Failed to connect`
**Possible Causes:**
- **PLC IP/Port mismatch**: Verify the PLC's IP address and Port (default `8501`).
- **Network Firewall**: Check if your OS or hardware firewall blocks TCP/UDP 8501.
- **PLC Config**: Ensure "Host Link (Upper Link)" is enabled in the Ethernet unit settings in KV Studio.
- **TCP/UDP Mismatch**: The library and PLC must use the same transport protocol.

### `HostLinkConnectionError: Timeout`
**Possible Causes:**
- **Cable Issue**: Check the Ethernet cable and hub.
- **Wrong IP**: The target IP might not be reachable. Try `ping <IP>`.
- **Busy PLC**: High-frequency communication might saturate old Ethernet units. Consider lowering the request frequency or using UDP.

---

## Protocol Errors (`HostLinkError`)

### `E1: Abnormal command`
**Occurs when:** The PLC received a command it doesn't support or understand.
**Solutions:**
- **Bit Write Restriction**: Many KV PLCs do not support `WR MR0 1`. Use `forced_set("MR0")` or `forced_reset("MR0")` instead.
- **Model Limitation**: Some older CPUs do not support certain commands (e.g., `URD` expansion access).
- **Format Mismatch**: Using `.D` or `.L` suffixes on devices that don't support 32-bit (rare, but possible).

### `E0: Abnormal device No.`
**Occurs when:** The specified device address does not exist on this PLC.
**Solutions:**
- **Out of Range**: Accessing `DM99999` on a CPU that only has 32,768 words.
- **Invalid Prefix**: Using prefixes not supported by the model (e.g., `EM` or `FM`).
- **Timer/Counter**: Accessing `T0` when it hasn't been used or initialized in the ladder program.

### `E4: Write disabled`
**Occurs when:** The CPU is locked or memory protection is on.
**Solutions:**
- **CPU Lock**: Check if the PLC has a memory protection switch or password set in KV Studio.

---

## Unexpected Data

### Value Mismatch (Endian Issues)
**Symptoms:** Reading `32-bit (.D/.L)` values gives strange results.
**Analysis:** Keyence stores 32-bit values with the **Low-word first** (e.g., DM100=Low, DM101=High).
**Solutions:** The library handles this automatically when using `.D` or `.L`. Do not try to manually swap words unless you have a non-standard ladder configuration.

### Float Handling
**Note:** Host Link is an ASCII protocol and doesn't natively return "float" tokens.
**Solutions:** Read the data as `.D` or `.L` and use Python's `struct` module to convert the bits to a floating-point value.
