"""
Setup script for PaperPal
Install this package to use 'paper' command globally
"""

import os
from pathlib import Path

from setuptools import find_packages, setup

# Read README for long description
readme_file = Path(os.path.join(str(Path(__file__).parent), "README.md"))
long_description = (
    readme_file.read_text(encoding="utf-8") if readme_file.exists() else ""
)

setup(
    name="PaperPal",
    version="1.0.0",
    author="Shenzhi-Wang",
    description="PaperPal - Discover and analyze arXiv papers with AI",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Shenzhi-Wang/PaperPal",
    packages=find_packages(),
    py_modules=["cli", "config", "main"],
    install_requires=[
        "arxiv>=2.0.0",
        "openai>=1.0.0",
        "python-dotenv>=1.0.0",
        "rich>=13.0.0",
        "prompt_toolkit>=3.0.0",
        "dateparser>=1.2.0",
        "pydantic>=2.0.0",
        "requests>=2.25.0",
    ],
    entry_points={
        "console_scripts": [
            "paper=cli:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
)
