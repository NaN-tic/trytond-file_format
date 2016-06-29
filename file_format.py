# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
import logging
import os.path
import traceback
import unicodedata
from simpleeval import simple_eval

from trytond.model import ModelSQL, ModelView, fields
from trytond.pool import Pool
from trytond.pyson import Eval, Greater, Not
from trytond.rpc import RPC

from jinja2 import Template as Jinja2Template


__all__ = ['FileFormat', 'FileFormatField']


def unaccent(text):
    if isinstance(text, str):
        text = unicode(text, 'utf-8')
    elif isinstance(text, unicode):
        pass
    else:
        return str(text)
    return unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore')


class FileFormat(ModelSQL, ModelView):
    '''File Format'''
    __name__ = 'file.format'

    name = fields.Char('Name', required=True, select=True)
    path = fields.Char('Path', states={
            'required': Eval('state') == 'active',
            }, depends=['state'],
        help='The path to the file name. The last slash is not necessary.')
    file_name = fields.Char('File Name', required=True)
    file_type = fields.Selection([
            ('csv', 'CSV'),
            ('xml', 'XML'),
            ], 'File Type', required=True,
        help='Choose type of file that will be generated')
    header = fields.Boolean('Header', states={
            'invisible': Eval('file_type') != 'csv',
            }, depends=['file_type'], help='Header (fields name) on files.')
    separator = fields.Char('Separator', size=1, states={
            'invisible': Eval('file_type') == 'xml',
            }, depends=['file_type'], help=('Put here, if it\'s necessary, '
            'the separator between each field.'))
    quote = fields.Char('Quote', size=1, states={
            'invisible': Eval('file_type') != 'csv',
            }, depends=['file_type'], help='Character to use as quote.')
    model = fields.Many2One('ir.model', 'Model', required=True)
    xml_format = fields.Text('XML Format', states={
            'invisible': Eval('file_type') != 'xml',
            }, depends=['file_type'])
    state = fields.Selection([
            ('active', 'Active'),
            ('disabled', 'Disabled'),
            ], 'State', required=True, select=True)
    fields = fields.One2Many('file.format.field', 'format', 'Fields',
        states={
            'invisible': Eval('file_type') != 'csv',
        }, depends=['file_type'])

    @classmethod
    def __setup__(cls):
        super(FileFormat, cls).__setup__()
        cls.__rpc__.update({
                'export_file': RPC(instantiate=0),
                })
        cls._error_messages.update({
            'path_not_exists': ('The Path "%(path)s" of File Format '
                '"%(file_format)s" doesn\'t exists.'),
            'path_no_permission': ('The Tryton server user '
                'doesn\'t have enough permissions over the Path "%(path)s" of '
                'File Format "%(file_format)s".\n'
                'Please, contact with your server administrator.'),
            'file_type_not_exisit': ('This file type "%/file_type)s" selected '
                'in file format "%(file_format)s" dosen\'t exist.'),
            })

    @staticmethod
    def default_quote():
        return ''

    @staticmethod
    def default_state():
        return 'disabled'

    @staticmethod
    def default_separator():
        return ''

    @staticmethod
    def default_file_type():
        return 'csv'

    @staticmethod
    def default_xml_format():
        return '<?xml version="1.0" encoding="utf-8"?>\n'

    @classmethod
    def validate(cls, file_formats):
        super(FileFormat, cls).validate(file_formats)
        cls.check_file_path(file_formats)

    @classmethod
    def view_attributes(cls):
        return [('/form/notebook/page[@id="csv_fields"]', 'states', {
                    'invisible': Eval('file_type') != 'csv',
                    })]

    @classmethod
    def check_file_path(cls, file_formats):
        for file_format in file_formats:
            if not file_format.path or file_format.state == 'disabled':
                continue
            if not os.path.isdir(file_format.path):
                cls.raise_user_error('path_not_exists', {
                        'path': file_format.path,
                        'file_format': file_format.rec_name,
                        })
            if (not os.access(file_format.path, os.R_OK)
                    or not os.access(file_format.path, os.W_OK)):
                cls.raise_user_error('path_no_permission', {
                        'path': file_format.path,
                        'file_format': file_format.rec_name,
                        })

    @property
    def eval_context(self):
        'Returns the context used for simple_eval'
        return {
            'len': len,
            }

    def export_file(self, instance_ids):
        if self.file_type == 'csv':
            self.export_csv(instance_ids)
        elif self.file_type == 'xml':
            self.export_xml(instance_ids)
        else:
            self.raise_user_error('file_type_not_exisit', {
                    'file_type': self.file_type,
                    'file_format': self.name,
                    })

    def export_csv(self, instance_ids):
        pool = Pool()
        Model = pool.get(self.model.model)

        header_line = []
        lines = []
        for instance in Model.browse(instance_ids):
            fields = []
            headers = []
            eval_context = self.eval_context.copy()
            eval_context.update({'instance': instance})
            for field in self.fields:
                try:
                    if field and field.expression:
                        field_eval = simple_eval(field.expression.replace('$',
                                'instance.'), **eval_context)
                    else:
                        field_eval = ''
                except:
                    field_eval = ''
                    logging.getLogger('file.format').warning('Exception '
                        'evaluating expression of field %s (%s) from File '
                        'Format %s (%s) for instance %s (%s):\n%s' % (
                            field.rec_name, field.id, self.rec_name, self.id,
                            instance.rec_name, instance.id,
                            traceback.format_exc()))

                if isinstance(field_eval, (int, float)):
                    if field.number_format:
                        field_eval = field.number_format % field_eval
                    if field.decimal_character:
                        field_eval = str(field_eval).replace('.',
                            unaccent(field.decimal_character) or '')

                ffield = unaccent(field_eval)
                # If the length of the field is 0, it's means that dosen't
                # matter how many chars it take
                if field.length > 0:
                    if field.align == 'right':
                        ffield = ffield.rjust(field.length,
                            unaccent(field.fill_character))
                    else:
                        ffield = ffield.ljust(field.length,
                            unaccent(field.fill_character))
                    ffield = ffield[:field.length]

                field_header = unaccent(field.name)
                if self.quote:
                    if self.quote == '"':
                        ffield = ffield.replace('"', "'")
                    elif self.quote == "'":
                        ffield = ffield.replace("'", '"')
                    ffield = self.quote + ffield + self.quote
                    field_header = self.quote + field_header + self.quote

                fields.append(ffield)
                headers.append(field_header)

            separator = self.separator or ''
            lines.append(separator.join(fields))
            if not header_line:
                header_line.append(separator.join(headers))

        try:
            file_path = self.path + "/" + self.file_name
            # Control if we need the headers + if the path file doesn't exists
            # and is a file. To add the headers or not
            if self.header and not os.path.isfile(file_path):
                # Write the headers in the file
                with open(file_path, 'w') as output_file:
                    for header in header_line:
                        output_file.write(header + "\r\n")

            # Put the inselfion in the file
            with open(file_path, 'a+') as output_file:
                for line in lines:
                    output_file.write(line + "\r\n")
            logging.getLogger('file.format').info('The file "%s" is write '
                'correctly' % self.file_name)
        except:
            pass

    def export_xml(self, instance_ids):
        pool = Pool()
        Model = pool.get(self.model.model)

        for instance in Model.browse(instance_ids):
            template = Jinja2Template(self.xml_format)
            xml = template.render({'record': instance}).encode('utf-8')
            try:
                file_path = self.path + "/" + str(instance.id) + self.file_name
                with open(file_path, 'w') as output_file:
                    output_file.write(xml)
                logging.getLogger('file.format').info('The file "%s" is write '
                    'correctly' % self.file_name)
            except:
                pass


class FileFormatField(ModelSQL, ModelView):
    '''File Format Field'''
    __name__ = 'file.format.field'
    format = fields.Many2One('file.format', 'Format', required=True,
        select=True, ondelete='CASCADE')
    name = fields.Char('Name', size=None, required=True, select=True,
        help='The name of the field. It\'s used if you have selected the '
        'Header checkbox.')
    sequence = fields.Integer('Sequence', required=True,
        help='The order that you want for the field\'s column in the file.')
    length = fields.Integer('Length',
        help='Set 0 if there isn\'t any required length for the field.')
    fill_character = fields.Char('Fill Char', size=1, states={
            'required': Greater(Eval('length', 0), 0),
            'readonly': Not(Greater(Eval('length', 0), 0)),
            }, depends=['length'],
        help='If you set a specific length, this character will be used to '
        'fill the field until the specified length.')
    align = fields.Selection([
            (None, ''),
            ('left', 'Left'),
            ('right', 'Right'),
            ], 'Align',
        states={
            'readonly': Not(Greater(Eval('length', 0), 0)),
            }, depends=['length'],
        help='If you set a specific length, you can decid the alignment of '
        'the value.')
    number_format = fields.Char('Number Format',
        help='Expression to format as string an integer or float field.\n'
        'E.g: if you have a float and want 2 decimals, write here "%.2f" '
        '(without quotes).')
    decimal_character = fields.Char('Decimal Character', size=1,
        help='If you need and specific decimal character for the float fields')
    expression = fields.Text('Expression',
        help='Python code for field processing. The fields are called like '
        '"$field_name" (without quotes).')

    @classmethod
    def __setup__(cls):
        super(FileFormatField, cls).__setup__()
        cls._order.insert(0, ('sequence', 'ASC'))

    @staticmethod
    def default_sequence():
        return 1

    @staticmethod
    def default_length():
        return 0

    @staticmethod
    def default_fill_character():
        return ''

    @staticmethod
    def default_align():
        return 'left'
