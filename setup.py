import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="hazus",
    version="0.0.10",
    author="James Raines",
    author_email="james.rainesii@fema.dhs.gov,usharma@niyamit.com",
    description="FEMA - Hazus Open-Source Library",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/nhrap-hazus/hazus.git",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
)