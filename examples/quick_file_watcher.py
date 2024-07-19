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

    # Set up file system watcher
    watcher = sandbox.filesystem.watch_dir(".")

    async def on_file_change(event):
        print(f"File change detected: {event.operation} on {event.path}")

    watcher.add_event_listener(on_file_change)
    await watcher.start()

    print("File system watcher started. Performing file operations...")

    # File operations to trigger the watcher
    await sandbox.filesystem.write(
        "test.txt", "This is a test file created by Firebox!"
    )
    print("Created test.txt")
    await asyncio.sleep(1)  # Give the watcher time to detect the change

    await sandbox.filesystem.write("test.txt", "This file has been modified!")
    print("Modified test.txt")
    await asyncio.sleep(1)  # Give the watcher time to detect the change

    await sandbox.filesystem.remove("test.txt")
    print("Removed test.txt")
    await asyncio.sleep(1)  # Give the watcher time to detect the change

    # Create a directory and a file inside it
    await sandbox.filesystem.make_dir("test_dir")
    print("Created test_dir")
    await asyncio.sleep(1)  # Give the watcher time to detect the change

    await sandbox.filesystem.write("test_dir/nested_file.txt", "This is a nested file")
    print("Created nested_file.txt inside test_dir")
    await asyncio.sleep(1)  # Give the watcher time to detect the change

    # List files to verify our operations
    files = await sandbox.filesystem.list(".")
    print("\nFiles in current directory:")
    for file in files:
        print(f"{'Directory' if file.is_dir else 'File'}: {file.name}")

    # Stop the watcher
    await watcher.stop()
    print("File system watcher stopped")

    # Release the sandbox
    await sandbox.release()
    print("Sandbox released.")


asyncio.run(main())
