import setuptools


with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()


setuptools.setup(
    name = "inspec",
    version = "0.2",
    packages = [
        "inspec",
        "inspec.gui",
    ],
    include_package_data = True,
    description = "Printing and viewing spectrograms of audio files in command line",
    author = "Kevin Yu",
    author_email = "thekevinyu@gmail.edu",
    license="MIT",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url = "https://github.com/kevinyu/inspec",
    keywords = "spectrogram audio visualization sound terminal",
    classifiers = [
        "Development Status :: 4 - Beta",
        "Programming Language :: Python :: 3.0",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    install_requires = [
        "Click",
        "SoundFile",
        "numpy",
        "sounddevice",
        "wheel",
        "windows-curses;platform_system=='Windows'",
    ],
    entry_points="""
        [console_scripts]
        inspec=inspec.cli:cli
    """,
    python_requires=">=3.6",
)
