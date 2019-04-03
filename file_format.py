# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
import logging
import os.path
import unicodedata
from trytond.model import ModelSQL, ModelView, fields
from trytond.pool import Pool
from trytond.pyson import Eval, Greater, Not
from trytond.i18n import gettext
from trytond.exceptions import UserError
from trytond.rpc import RPC
from trytond.transaction import Transaction
from genshi.template import TextTemplate
from jinja2 import Template as Jinja2Template


__all__ = ['FileFormat', 'FileFormatField']

logger = logging.getLogger(__name__)
_ENGINES = [
    ('python', 'Python'),
    ('genshi', 'Genshi'),
    ('jinja2', 'Jinja2')
    ]


def unaccent(text):
    if isinstance(text, bytes):
        text = str(text, 'utf-8')
    elif not isinstance(text, str):
        return str(text)
    return (unicodedata.normalize('NFKD', text)
        .encode('ascii', 'ignore')
        .decode('ascii'))


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
    ffields = fields.One2Many('file.format.field', 'format', 'Fields',
        states={
            'invisible': Eval('file_type') != 'csv',
        }, depends=['file_type'])
    engine = fields.Selection(_ENGINES, 'Engine', required=True)

    @classmethod
    def __setup__(cls):
        super(FileFormat, cls).__setup__()
        cls.__rpc__.update({
                'export_file': RPC(instantiate=0),
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

    @staticmethod
    def default_engine():
        return 'jinja2'

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
                raise UserError(gettext('file_format.msg_path_not_exists',
                    path=file_format.path,
                    file_format=file_format.rec_name,
                    ))
            if (not os.access(file_format.path, os.R_OK)
                    or not os.access(file_format.path, os.W_OK)):
                raise UserError(gettext('file_format.msg_path_no_permission',
                    path=file_format.path,
                    file_format=file_format.rec_name,
                    ))

    @classmethod
    def eval(cls, expression, record, engine='genshi'):
        '''Evaluates the given :attr:expression

        :param expression: Expression to evaluate
        :param record: The browse record of the record
        '''
        engine_method = getattr(cls, '_engine_' + engine)
        return engine_method(expression, record)

    @staticmethod
    def template_context(record):
        """Generate the tempalte context

        This is mainly to assist in the inheritance pattern
        """
        User = Pool().get('res.user')

        user = None
        if Transaction().user:
            user = User(Transaction().user)
        return {
            'record': record,
            'user': user,
            }

    @classmethod
    def _engine_python(cls, expression, record):
        '''Evaluate the pythonic expression and return its value
        '''
        if expression is None:
            return ''

        assert record is not None, 'Record is undefined'
        template_context = cls.template_context(record)
        return eval(expression, template_context)

    @classmethod
    def _engine_genshi(cls, expression, record):
        '''
        :param expression: Expression to evaluate
        :param record: Browse record
        '''
        if not expression:
            return ''

        template = TextTemplate(expression)
        template_context = cls.template_context(record)
        return template.generate(**template_context).render(encoding='UTF-8')

    @classmethod
    def _engine_jinja2(cls, expression, record):
        '''
        :param expression: Expression to evaluate
        :param record: Browse record
        '''
        if not expression:
            return ''

        template = Jinja2Template(expression)
        template_context = cls.template_context(record)
        return template.render(template_context)

    def export_file(self, records):
        if self.file_type == 'csv':
            self.export_csv(records)
        elif self.file_type == 'xml':
            self.export_xml(records)
        else:
            raise UserError(gettext('file_format.msg_file_type_not_exisit',
                file_type=self.file_type,
                file_format=self.name,
                ))

    def export_csv(self, records):
        path = self.path
        if not path:
            raise UserError(gettext('file_format.msg_path_not_exists',
                path='',
                file_format=self.rec_name,
                ))

        header_line = []
        lines = []
        for record in records:
            fields = []
            headers = []
            for field in self.ffields:
                if field and field.expression:
                    field_eval = self.eval(
                        field.expression, record, self.engine)
                    if field.number_format:
                        if field_eval.isdigit():
                            field_eval = field.number_format % int(field_eval)
                        else:
                            field_eval = (
                                field.number_format % float(field_eval))
                    if field.decimal_character:
                        field_eval = str(field_eval).replace('.',
                            unaccent(field.decimal_character) or '')
                else:
                    field_eval = ''

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
            file_path = path + "/" + self.file_name
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
            logger.info('The file "%s" is write correctly' % self.file_name)
        except:
            logger.error('Can not write file "%s" correctly' % self.file_name)

    def export_xml(self, records):
        path = self.path
        if not path:
            raise UserError(gettext('file_format.msg_path_not_exists',
                path='',
                file_format=self.rec_name,
                ))

        for record in records:
            xml = self.eval(self.xml_format, record, self.engine)
            try:
                file_path = path + "/" + str(record.id) + self.file_name
                with open(file_path, 'w') as output_file:
                    output_file.write(xml)
                logger.info(
                    'The file "%s" is write correctly' % self.file_name)
            except:
                logger.error(
                    'Can not write file "%s" correctly' % self.file_name)


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
