# gpu-monitor

A Python tool for polling remote GPU server and sending a notification when GPUs are available.

## Requirements

## Getting started

Basic usage - notify when 4 fully idle GPUs are available

```
python gpu-monitor.py -u <user@host> --min_gpus 4 --alert_sound <path/to/sound/file>
```

Screenshot of notification on Ubuntu 20.04:
