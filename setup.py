from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="admz",
    version="2.0.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="ADMZ (Axis Device Manager) - Backend-agnostic credential management system for Axis devices",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/admz",
    packages=find_packages(exclude=["tests", "examples", "docs"]),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Security",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.8",
    install_requires=[
        "hvac>=2.0.0",  # HashiCorp Vault client
        "cryptography>=41.0.0",  # Password encryption for SQLite backend
        "flask>=3.0.0",  # Web UI framework
    ],
    extras_require={
        "discovery": [
            "zeroconf>=0.131.0",
            "async-upnp-client>=0.40.0",
            "WSDiscovery>=2.0.0",
            "httpx>=0.27.0",
            "scapy>=2.5.0",
            "pysnmp>=6.0.0",
        ],
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "pytest-mock>=3.10.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
            "mypy>=1.0.0",
        ],
    },
)
