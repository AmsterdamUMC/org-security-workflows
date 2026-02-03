from setuptools import setup, find_packages

setup(
    name="aumc-security-hooks",
    version="1.0.0",
    description="Amsterdam UMC GitHub security pre-commit hooks",
    packages=["pre_commit_check"],
    package_dir={"pre_commit_check": "pre-commit-check"},
    entry_points={
        "console_scripts": [
            "check_filetypes=pre_commit_check.check_filetypes:main",
            "check_personal_info=pre_commit_check.check_personal_info:main",
        ],
    },
    python_requires=">=3.8",
)