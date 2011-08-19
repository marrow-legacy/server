# encoding: utf-8

"""Release information about Marrow Server."""

from collections import namedtuple


__all__ = ['version_info', 'version']


version_info = namedtuple('version_info', ('major', 'minor', 'micro', 'releaselevel', 'serial'))(0, 9, 0, 'final', 0)

version = ".".join([str(i) for i in version_info[:3]]) + ((version_info.releaselevel[0] + str(version_info.serial)) if version_info.releaselevel != 'final' else '')


name = "marrow.server"
version = "0.9"
release = "0.9"

summary = "Abstract asynchronous, multi-process socket server API."
description = """"""
author = "Alice Bevan-McGregor"
email = "alice+marrow@gothcandy.com"
url = "http://github.com/pulp/marrow.server"
download_url = "http://cheeseshop.python.org/pypi/marrow.server/"
copyright = "2010, Alice Bevan-McGregor"
license = "MIT"
