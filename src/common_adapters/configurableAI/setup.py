"""
Setup script for ConfigurableAI package.
"""

from setuptools import setup, find_packages

setup(
    name="configurable-ai",
    version="1.0.0",
    description="A common package for switching between AI providers",
    author="Forgex Team",
    packages=find_packages(),
    install_requires=[
        "openai>=1.0.0",
        "google-cloud-aiplatform>=1.0.0",
        "numpy>=1.20.0",
    ],
    extras_require={
        "dev": [
            "pytest>=6.0.0",
            "pytest-asyncio>=0.18.0",
            "black>=22.0.0",
            "flake8>=4.0.0",
        ]
    },
    python_requires=">=3.8",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)