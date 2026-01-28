from setuptools import setup

setup(
    name="aumc-security-hooks",
    version="1.0.0",
    description="Amsterdam UMC GitHub security pre-commit hooks",
    package_dir={"": "pre-commit-check"},
    py_modules=["check_filetypes", "check_personal_info"],
    entry_points={
        "console_scripts": [
            "check_filetypes=check_filetypes:main",
            "check_personal_info=check_personal_info:main",
        ],
    },
    python_requires=">=3.8",
)