import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="containedenv",
    version="0.0.1",
    author="Adam Ferreira",
    author_email="adam.ferreira.dc@gmail.com",
    description="Dev containers creation tool",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/adamferreira/containedenv",
    project_urls={},
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    package_dir={
        "containedenv": "containedenv"
    },
    packages = ["containedenv"], 
    python_requires=">=3.0",
    install_requires=[
       "pyyaml",
       "docker",
       "pyrc @ git+https://github.com/adamferreira/pyrc.git@master"
   ],
    entry_points= {
            "console_scripts": [
                "containedenv = containedenv.__main__:main"
        ]
    }
)