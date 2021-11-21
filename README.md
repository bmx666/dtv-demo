Device Tree Visualizer

### requirements

1. python3 -m pip install -r requirements.txt
2. cpp
3. dtc or [patched dtc](https://github.com/bmx666/dtc)

Patched dtc version replaces deleted nodes and deleted properties with empty nodes and properties with same name + suffix " \_DELETED\_ " for parsing.
