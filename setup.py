from setuptools import setup, find_packages
import os

version = '0.1'

setup(name='imio.trac2taskjuggler',
      version=version,
      description="Generates taskjuggler content files from trac milestones",
      long_description=open("README.rst").read() + "\n",
      # Get more strings from
      # http://pypi.python.org/pypi?:action=list_classifiers
      classifiers=[
        "Programming Language :: Python",
        ],
      keywords='trac taskjuggler',
      author='IMIO',
      author_email='support@imio.be',
      url='http://github.com/IMIO/',
      license='GPL',
      packages=find_packages(exclude=['ez_setup']),
      namespace_packages=['imio'],
      include_package_data=True,
      zip_safe=False,
      install_requires=[
          'setuptools',
          'imio.pyutils',
          'jinja2',
          'psycopg2',
      ],
      entry_points="""
      [console_scripts]
      generate_tj = imio.trac2taskjuggler.main:generate
      """,
      )
