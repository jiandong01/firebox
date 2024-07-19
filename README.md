# Firebox: Secure Sandbox Environment

Firebox is a powerful sandbox environment for running code securely. It provides a controlled and isolated execution environment, making it ideal for running untrusted code, testing, and secure development workflows.

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Features](#features)
- [API Reference](#api-reference)
  - [Sandbox](#sandbox)
  - [Filesystem](#filesystem)
  - [Process](#process)
  - [Terminal](#terminal)
  - [Code Snippet](#code-snippet)
- [Advanced Usage](#advanced-usage)
- [Configuration](#configuration)
- [Contributing](#contributing)
- [License](#license)

## Installation

To install Firebox, use pip:

```bash
pip install firebox
```

## Quick Start

Here's a simple example to get you started with Firebox:

```python
import asyncio
from firebox import Sandbox

async def main():
    # Create a new sandbox
    sandbox = Sandbox()

    # Wait for the sandbox to be fully initialized
    while sandbox.status != SandboxStatus.RUNNING:
        await asyncio.sleep(0.1)

    # Execute a command in the sandbox
    result = await sandbox.process.start_and_wait("echo 'Hello, Firebox!'")
    print(f"Output: {result.stdout}, Exit Code: {result.exit_code}")

    # Release the sandbox
    await sandbox.release()

asyncio.run(main())
```

## Features

- Secure execution environment based on Docker
- Persistent storage with automatic mounting
- File system operations
- Process management
- Terminal emulation
- Environment variable control
- Customizable Docker images
- Timeout controls
- Port scanning and management

## API Reference

### Sandbox

#### Creating a Sandbox

```python
from firebox import Sandbox
from firebox.models import DockerSandboxConfig, SandboxStatus

config = DockerSandboxConfig(
    image="kalilinux/kali-rolling",
    cpu=1,
    memory="2g",
    environment={"TEST_ENV": "test_value"},
    persistent_storage_path="./sandbox_data",
    cwd="/sandbox"
)

sandbox = Sandbox(template=config)

# Wait for the sandbox to be fully initialized
while sandbox.status != SandboxStatus.RUNNING:
    await asyncio.sleep(0.1)
```

#### Closing a Sandbox

```python
await sandbox.close()
```

### Filesystem

#### Writing Files

```python
await sandbox.filesystem.write("test.txt", "Hello, Firebox!")
```

#### Reading Files

```python
content = await sandbox.filesystem.read("test.txt")
```

#### Listing Directory Contents

```python
files = await sandbox.filesystem.list(".")
```

### Process

#### Starting a Process

```python
process = await sandbox.process.start("python3 script.py")
```

#### Waiting for Process Completion

```python
result = await process.wait()
```

#### Sending Input to a Process

```python
await process.send_stdin("input data\n")
```

### Terminal

#### Starting a Terminal Session

```python
terminal = await sandbox.terminal.start(
    on_data=lambda data: print(f"Received: {data}"),
    cols=80,
    rows=24
)
```

#### Sending Data to Terminal

```python
await terminal.send_data("ls -l\n")
```

### Code Snippet

#### Adding a Custom Script

```python
await sandbox.code_snippet.add_script("my_script.sh", "#!/bin/bash\necho 'Hello from custom script!'")
```

#### Listing Custom Scripts

```python
scripts = await sandbox.code_snippet.list_scripts()
```

## Advanced Usage

### Custom Docker Images

You can use custom Docker images by specifying them in the `DockerSandboxConfig`:

```python
config = DockerSandboxConfig(
    dockerfile="/path/to/Dockerfile",
    dockerfile_context="/path/to/context",
    persistent_storage_path="./sandbox_data",
    cwd="/sandbox"
)
sandbox = Sandbox(template=config)
```

### Watching for File Changes

```python
def on_file_change(event):
    print(f"File changed: {event.path}")

watcher = sandbox.filesystem.watch_dir(".")
watcher.add_event_listener(on_file_change)
await watcher.start()
```

## Configuration

Firebox can be configured using a YAML file. Create a `firebox_config.yaml` file in your project directory:

```yaml
sandbox_image: "firebox-sandbox:latest"
container_prefix: "firebox-sandbox"
persistent_storage_path: "./sandbox_data"
cpu: 1
memory: "1g"
timeout: 30
docker_host: "unix://var/run/docker.sock"
debug: false
log_level: "INFO"
max_retries: 3
retry_delay: 1.0
```

## Contributing

We welcome contributions to Firebox! Please see our [Contributing Guide](CONTRIBUTING.md) for more details.

## License

Firebox is released under the MIT License.
