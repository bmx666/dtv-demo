Device Tree Visualizer

### requirements

1. python3 -m pip install -r requirements.txt
2. cpp
3. dtc or [patched dtc](https://github.com/bmx666/dtc)

Patched dtc version append tag "\_\_\[|\>\*DELETED\*\<|\]\_\_" into comment (list of files) for deleted nodes and properties.

### config file - dtv.conf

* set your preferred editor in env `editor_cmd`
* include extra dts paths into list `include_dir_stubs`
