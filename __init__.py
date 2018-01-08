# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool
from . import file_format


def register():
    Pool.register(
        file_format.FileFormat,
        file_format.FileFormatField,
        module='file_format', type_='model')
