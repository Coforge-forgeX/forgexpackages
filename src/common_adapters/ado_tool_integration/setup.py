from setuptools import setup, find_packages

setup(
    name="ado_tool_integration",
    version="0.1.0",
    description="Azure DevOps integration tools for multi-agent systems",
    python_requires=">=3.10",
    packages=["ado_tool_integration"],
    package_dir={"ado_tool_integration": "."},
    install_requires=[
        "azure-devops>=7.1.0b4",
        "msrest>=0.7.1",
        "cachetools>=5.3.0",
        "langchain-core>=0.1.0",
    ],
)
