from setuptools import setup, find_packages

setup(
    name="trading_bot",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "pandas",
        "ccxt",
        "python-dotenv",
    ],
    python_requires=">=3.8",
) 