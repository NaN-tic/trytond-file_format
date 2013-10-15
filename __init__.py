#The COPYRIGHT file at the top level of this repository contains the full
#copyright notices and license terms.

from trytond.pool import Pool
from .file_format import *


def register():
    Pool.register(
        FileFormat,
        FileFormatField,
        module='file_format', type_='model')
