from setuptools import setup, find_packages

setup(
    name="download_response",
    version="0.1.0",
    description="Response download tools for converting messages to various formats",
    python_requires=">=3.10",
    packages=["download_response"],
    package_dir={"download_response": "."},
    install_requires=[
        "python-docx>=0.8.11",
        "beautifulsoup4>=4.11.0",
        "markdown-it-py>=2.0.0",
        "requests>=2.28.0",
        "Pillow>=9.0.0",
    ],
)
