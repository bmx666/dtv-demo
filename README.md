# Device Tree Visualizer

## Ported to PyQt6, old PyQt5 is not supported (see locked branch [pyqt5](https://github.com/bmx666/dtv-demo/tree/pyqt5))

## screenshots

DTV with original dtc

![DTV with original dtc](screenshot/dtv-demo_dtc_original.png?raw=true "DTV with original dtc")

DTV with patched dtc

![DTV with patched dtc](screenshot/dtv-demo_dtc_patched.png?raw=true "DTV with patched dtc")

DTV with overlays

![DTV with overlays](screenshot/dtv-demo_overlays.png?raw=true "DTV with overlays")

## requirements

1. python3 -m pip install -r requirements.txt<br>
_for Ubuntu 16.04_: in `requirements.txt` set `PyQt5==5.14.0`
3. cpp >= 5.4.0
4. dtc >= 1.5.0 (must support `--annotate` flag) or [patched dtc](https://github.com/bmx666/dtc)

Patched dtc version add extra annotate flags:
* show full list of sources for properties
* prepend comment `/* __[|>*DELETED*<|]__ */` for deleted nodes, labels or properties and comment out them all
* mark all childs of deleted nodes as deleted and do not remove childs

## config file - dtv.conf

* set your preferred editor in env `editor_cmd`
* include extra dts paths into list `include_dir_stubs`

## command line usage

* open dts

```
python3 dtv.py /path/to/some.dts
```

* display final dts with applied overlays on base dts

```
python3 dtv.py /path/to/base.dts /path/to/overlay1.dts /path/to/overlay2.dts
```

## overlays

### Linux

```
/ {
  fragment@0 {
    target = <&some_node>;
      __overlay__ {
        some_prop = "okay";
        ...
      };
  };
};
```

DTV supports feature to automatically generate temporary overlays by using [ovmerge util from Rasberry Pi](https://github.com/raspberrypi/utils) and [included modified Python fdt library](https://github.com/molejar/pyFDT)

### Android

Google strongly recommends you do not use `fragment@x` and syntax `__overlay__`, and instead use the reference syntax. For example:

```
&some_node {
  some_prop = "okay";
  ...
};
```

#### Solution for display final overlays

Include base and overlays into temporary dts-file and remove from overlays `/dts-v1/;` and `/plugin/;`

```
#include "base.dts"
#include "overlay1.dts"
#include "overlay2.dts"
```

*TBD: automatically generate temporary file*

[See more](https://source.android.com/devices/architecture/dto/syntax)
