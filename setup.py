import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="kube-workload-restarter",
    version="0.0.1",
    author="Andrea Cioni",
    description="Automate your weekly menu with AI",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/andreacioni/kube-workload-restarter",
    packages=setuptools.find_packages(),
    classifiers=(
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ),
)
