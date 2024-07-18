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
from firebox import Sandbox

async def main():
    # Create a new sandbox
    sandbox = await Sandbox.create()

    # Execute a command in the sandbox
    result, exit_code = await sandbox.communicate("echo 'Hello, Firebox!'")
    print(f"Output: {result}, Exit Code: {exit_code}")

    # Close the sandbox
    await sandbox.close()

asyncio.run(main())
```

## Features

- Secure execution environment
- File system operations
- Process management
- Environment variable control
- Customizable Docker images
- Timeout controls

## API Reference

### Sandbox

#### Creating a Sandbox

```python
from firebox import Sandbox, SandboxConfig

config = SandboxConfig(
    image="fireenv-sandbox:latest",
    cpu=1,
    memory="1g",
    environment={"TEST_ENV": "test_value"},
)

sandbox = await Sandbox.create(config)
```

#### Executing Commands

```python
result, exit_code = await sandbox.communicate("ls -l")
```

#### Closing a Sandbox

```python
await sandbox.close()
```

### Filesystem

#### Writing Files

```python
await sandbox.filesystem.write("/tmp/test.txt", "Hello, Firebox!")
```

#### Reading Files

```python
content = await sandbox.filesystem.read("/tmp/test.txt")
```

#### Listing Directory Contents

```python
files = await sandbox.filesystem.list("/tmp")
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

## Advanced Usage

### Custom Docker Images

You can use custom Docker images by specifying them in the `SandboxConfig`:

```python
config = SandboxConfig(
    dockerfile="/path/to/Dockerfile",
    dockerfile_context="/path/to/context",
)
sandbox = await Sandbox.create(config)
```

### Watching for File Changes

```python
def on_file_change(event):
    print(f"File changed: {event['path']}")

watcher = sandbox.filesystem.watch_dir("/tmp")
watcher.add_event_listener(on_file_change)
watcher.start()
```

## Configuration

Firebox can be configured using a YAML file. Create a `firebox_config.yaml` file in your project directory:

```yaml
sandbox_image: "fireenv-sandbox:latest"
container_prefix: "fireenv-sandbox"
persistent_storage_path: "/persistent"
cpu: 1
memory: "1g"
timeout: 30
docker_host: "tcp://localhost:2375"
```

## Contributing

We welcome contributions to Firebox! Please see our [Contributing Guide](CONTRIBUTING.md) for more details.

## License

Firebox is released under the [MIT License](LICENSE).
