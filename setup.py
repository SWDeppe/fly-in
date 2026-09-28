"""Package configuration for Fly-in."""
import io
import os
from setuptools import find_packages, setup


def read(*paths: str, **kwargs: str) -> str:
    """Read a UTF-8 project file.
    >>> read("fly_in", "VERSION")
    '0.1.0'
    >>> read("README.md")
    ...
    """

    content = ""
    with io.open(
        os.path.join(os.path.dirname(__file__), *paths),
        encoding=kwargs.get("encoding", "utf8"),
    ) as open_file:
        content = open_file.read().strip()
    return content


def read_requirements(path: str) -> list[str]:
    dependencies: list[str] = []
    for line in read(path).split("\n"):
        line = line.strip()
        if line.startswith("./"):
            line = os.path.abspath(line)
            name: str = ""
            with open(line + "/pyproject.toml", "r", encoding="utf8") as f:
                content = f.read().strip()
                # print(content)
                if 'name' in content:
                    start = content.index('name') + 5
                    end = content.index('\n', start)
                    name = content[start + 3:end - 1].strip()
            line = f"{name} @ file://{line}"
        if line and not line.startswith(('"', "#", "-", "git+")):
            dependencies.append(line)

    return dependencies


setup(
    name="fly-in",
    version=read("fly_in", "VERSION"),
    description="Concurrent drone routing simulation.",
    long_description=read("README.md"),
    long_description_content_type="text/markdown",
    author="sdeppe",
    packages=find_packages(exclude=["tests", ".github"]),
    install_requires=read_requirements("requirements.txt"),
    entry_points={
        "console_scripts": ["fly-in = fly_in.__main__:main"]
    },
    extras_require={"test": read_requirements("requirements-test.txt")},
)
