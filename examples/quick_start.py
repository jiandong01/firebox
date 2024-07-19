import asyncio
from firebox import Sandbox
from firebox.models import SandboxStatus, FilesystemOperation


async def main():
    # Create a new sandbox
    sandbox = Sandbox(template="firebox-sandbox")  # Use default template

    # Wait for the sandbox to be fully initialized
    while sandbox.status != SandboxStatus.RUNNING:
        await asyncio.sleep(0.1)

    print("Sandbox is ready!")

    # Execute a simple command in the sandbox
    result = await sandbox.process.start_and_wait("echo 'Hello World!'")
    print(
        f"Simple command output: {result.stdout.strip()}, Exit Code: {result.exit_code}"
    )

    # File operations in the sandbox
    await sandbox.filesystem.write(
        "test.txt", "This is a test file created by Firebox!"
    )
    file_content = await sandbox.filesystem.read("test.txt")
    print(f"File content: {file_content.strip()}")

    # List files in the current directory
    files = await sandbox.filesystem.list(".")
    print("Files in current directory:")
    for file in files:
        print(f"{'Directory' if file.is_dir else 'File'}: {file.name}")

    # Watch for file changes
    watcher = sandbox.filesystem.watch_dir(".")

    def on_file_change(event):
        print(f"File change detected: {event.operation} on {event.path}")

    watcher.add_event_listener(on_file_change)
    await watcher.start()

    # Run a long-running process
    process = await sandbox.process.start("for i in {1..5}; do echo $i; sleep 1; done")

    # While the process is running, let's perform some other operations
    await sandbox.filesystem.write(
        "another_file.txt", "This file was created while a process was running!"
    )

    # Wait for the process to complete
    result = await process.wait()
    print(f"Long-running process output:\n{result.stdout}")

    # Use a terminal
    terminal = await sandbox.terminal.start(
        on_data=lambda data: print(f"Terminal output: {data.strip()}"), cols=80, rows=24
    )
    await terminal.send_data("ls -l\n")
    await asyncio.sleep(2)  # Wait a bit for the command to execute
    await terminal.kill()

    # Stop the file watcher
    await watcher.stop()

    # Release the sandbox
    await sandbox.release()
    print("Sandbox released.")


asyncio.run(main())
