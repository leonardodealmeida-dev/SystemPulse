# SystemPulse

**A lightweight desktop system monitor for Linux, built with Python, PySide6 and psutil.**

SystemPulse brings essential computer telemetry into one desktop application: processor activity, memory usage, storage capacity, network traffic, running processes and hardware information. It is designed to run locally without a cloud account.

> **Project status:** Beta (0.5). Features and interfaces may change. Test it on a non-critical system before relying on it for troubleshooting.

## Features

### Overview
- Live CPU and memory utilization.
- Per-logical-CPU usage bars.
- Storage utilization for the root filesystem.
- Network download and upload rates.
- Disk read/write throughput when the operating system exposes the counters.
- Short rolling history charts for CPU, memory and disk I/O.
- A compact summary of the operating system, logical CPUs, installed memory and uptime.

### Processes
- List running processes with PID, CPU and memory usage.
- Search by process name or PID.
- Sort by memory, CPU or process name.
- Double-click a process to inspect details such as status, memory, thread count and executable path.
- Process management actions are intentionally not provided in this beta.

### Hardware and system information
- Operating system, kernel and architecture.
- Processor model and logical/physical CPU counts when available.
- Installed memory, root filesystem capacity and system uptime.
- Temperature readings when supported by the hardware, kernel and permissions.

### Storage and network
- Mounted filesystem usage, including total, used and free space.
- Network interface names and available IPv4 address information in the app.
- Aggregate network traffic counters and current transfer rates.

### Settings and diagnostics
- Configurable metrics refresh interval.
- Keep the application window on top.
- Start minimized.
- Optional desktop-session autostart entry for the current Linux user.
- Show or hide temperature readings.
- Preferences saved locally with Qt `QSettings`.
- Export a diagnostic text report. The report is designed to omit IP addresses, hostnames, usernames and the running-process list.

## Screenshots

Screenshots will be added here as the interface is finalized.

## Requirements

- Linux desktop environment (Linux Mint XFCE is the initial development target).
- Python 3.10 or newer recommended.
- `python3-venv` and `python3-pip`.
- Python packages: `PySide6` and `psutil`.

Some hardware readings depend on Linux kernel interfaces, available sensors, drivers and user permissions. Temperature information may not be available on every computer.

## Installation

Clone the repository and enter its directory:

```bash
git clone <YOUR-GITHUB-REPOSITORY-URL>
cd SystemPulse
```

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install --upgrade pip
pip install PySide6 psutil
```

If the repository includes a maintained `requirements.txt`, you can install from it instead:

```bash
pip install -r requirements.txt
```

Run the application:

```bash
python main.py
```

## Usage notes

- Open **Overview** to watch live resource usage and history charts.
- Open **Processes** to search and inspect running programs. Double-click a row for more details.
- Open **Hardware**, **Storage** and **Network** for additional system information.
- Open **Settings** to change the refresh rate and local preferences.
- Use **Export system diagnostics** in Settings to save a text report for troubleshooting.

SystemPulse is intended to monitor the current user's computer. It does not need administrator privileges for its basic functionality. Some process and sensor details may be unavailable without additional permissions; do not run the app as root just to make every field appear.

## Privacy

SystemPulse performs monitoring locally. It does not require an online account or send telemetry to a remote service. The diagnostic report intentionally excludes several identifying details, but review any exported file before sharing it. Process details shown inside the application can include executable paths and the process account name.

## Development

The beta is currently organized around `main.py` to keep early development straightforward. As the project matures, the UI, monitoring services, settings and diagnostics can be separated into modules.

Potential future improvements include:

- Per-device disk and network views.
- More detailed sensor discovery.
- Configurable resource alerts.
- Unit and integration tests.
- Packaged releases for supported Linux distributions.

## Troubleshooting

**The temperature field says “Not available”**  
The hardware or driver may not expose readable temperature sensors to the operating system. This is not necessarily an application error.

**Some process details are missing**  
Linux may restrict access to information about processes owned by another user or protected by the system. SystemPulse handles many of these permission limits by skipping unavailable details.

**The disk I/O graph stays near zero**  
The graph shows changes in aggregate disk counters. A quiet system may have very little disk activity, and some virtual or special filesystems may not provide meaningful counters.

**The application does not start**  
Activate the virtual environment, install the dependencies, then run `python main.py` from the project directory. Check the terminal for the full error message.

## Contributing

Bug reports, feature suggestions and pull requests are welcome. For a useful bug report, include your Linux distribution, Python version, steps to reproduce the issue and the relevant error message. Remove personal information before sharing logs or diagnostic reports.

## License

No license has been selected yet. Until a license is added to this repository, the source code is publicly viewable but is not automatically granted the usual permissions to reuse, modify or redistribute it. Consider adding an MIT license if you want a simple permissive open-source license.
