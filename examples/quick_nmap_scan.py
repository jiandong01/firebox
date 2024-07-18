import asyncio
import os
from firebox import Sandbox, SandboxConfig


async def main():
    # Create a temporary directory for persistent storage
    persistent_storage_path = "./sandbox_data"
    os.makedirs(persistent_storage_path, exist_ok=True)

    config = SandboxConfig(
        image="kalilinux/kali-rolling",
        cpu=1,
        memory="2g",
        environment={"DEBIAN_FRONTEND": "noninteractive"},
        persistent_storage_path=persistent_storage_path,
        cwd="/sandbox",
    )

    sandbox = Sandbox(config)
    await sandbox.init()
    print("Sandbox created successfully")

    try:
        # Update package list
        print("Updating package list...")
        update_process = await sandbox.process.start("apt-get update")
        update_process.on_stdout = lambda output: print(
            f"Update output: {output.line.strip()}"
        )
        update_result = await update_process.wait()
        print(f"Update completed with exit code: {update_result['exit_code']}")

        # Install nmap
        print("Installing nmap...")
        install_process = await sandbox.process.start("apt-get install -y nmap")
        install_process.on_stdout = lambda output: print(
            f"Install output: {output.line.strip()}"
        )
        install_result = await install_process.wait()
        print(
            f"Nmap installation completed with exit code: {install_result['exit_code']}"
        )

        # Run nmap scan on localhost
        print("Running nmap scan...")
        scan_cmd = "nmap -sV -p- 127.0.0.1 -oN /sandbox/nmap_scan_results.txt"
        scan_process = await sandbox.process.start(scan_cmd)
        scan_process.on_stdout = lambda output: print(
            f"Scan output: {output.line.strip()}"
        )
        scan_result = await scan_process.wait()
        print(f"Nmap scan completed with exit code: {scan_result['exit_code']}")

        # Check if the scan results file exists
        file_exists = await sandbox.filesystem.exists("nmap_scan_results.txt")
        if not file_exists:
            print("Error: Nmap scan results file not found.")
            return

        # Read the scan results
        print("Reading scan results...")
        try:
            scan_results = await sandbox.filesystem.read("nmap_scan_results.txt")
            print("Scan Results:")
            print(scan_results)

            # The scan results file is already in the persistent storage,
            # so we don't need to download it separately.
            host_output_path = os.path.join(
                persistent_storage_path, "nmap_scan_results.txt"
            )
            print(f"Scan results are available at: {os.path.abspath(host_output_path)}")
        except FileNotFoundError:
            print("Error: Failed to read the scan results file.")
        except Exception as e:
            print(f"An error occurred: {str(e)}")

    finally:
        # Close the sandbox
        await sandbox.close()
        print("Sandbox closed")


if __name__ == "__main__":
    asyncio.run(main())
