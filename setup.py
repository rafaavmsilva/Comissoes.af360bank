from setuptools import setup, find_packages

setup(
    name="auth_client",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        "flask>=2.0.1",
        "requests>=2.26.0"
    ]
)
