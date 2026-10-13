from setuptools import setup, find_packages

setup(
    name='lrfhss',
    version='0.0.1',
    packages=find_packages(include=['lrfhss']),
    entry_points={'console_scripts': ['ntn-experiment=lrfhss.ntn_experiments:main']},
)