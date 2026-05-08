from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("docent-cli")
except PackageNotFoundError:
    __version__ = "dev"
