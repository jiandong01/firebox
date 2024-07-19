FROM python:3.11

# Set the working directory in the container
WORKDIR /sandbox

# Update the package lists and install some basic tools
RUN apt-get update && apt-get install -y \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Install any Python packages you might need
RUN pip3 install --no-cache-dir requests

# Create a non-root user
RUN useradd -m sandboxuser
USER sandboxuser

# Set the default command to run when starting the container
CMD ["/bin/bash"]