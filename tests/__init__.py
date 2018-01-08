# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
try:
    from trytond.modules.file_format.tests.test_file_format import suite
except ImportError:
    from .test_file_format import suite

__all__ = ['suite']
