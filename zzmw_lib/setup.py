from setuptools import setup, find_packages

setup(
    name="zzmw_common",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "apscheduler",
        "flask",
        "inotify-simple",
        "paho-mqtt",
        "systemd-python",
    ],
)


