#!/usr/bin/env python
# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
import os.path
import tempfile
import unittest
import trytond.tests.test_tryton
from trytond.tests.test_tryton import POOL, DB_NAME, USER, CONTEXT, test_view,\
    test_depends
from trytond.transaction import Transaction


class FileFormatTestCase(unittest.TestCase):
    '''
    Test File Format module.
    '''

    def setUp(self):
        trytond.tests.test_tryton.install_module('file_format')
        self.model = POOL.get('ir.model')
        self.file_format = POOL.get('file.format')
        self.file_format_field = POOL.get('file.format.field')

    def test0005views(self):
        '''
        Test views.
        '''
        test_view('file_format')

    def test0006depends(self):
        '''
        Test depends.
        '''
        test_depends()

    def test0010export_csv_file(self):
        '''
        Test FileFormat.export_file.
        '''
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            model_model, = self.model.search([
                    ('model', '=', 'ir.model'),
                    ])
            file_format_model, = self.model.search([
                    ('model', '=', 'file.format'),
                    ])
            temp_file = tempfile.NamedTemporaryFile()
            temp_file.close()

            file_format = self.file_format()
            file_format.name = 'CSV File Format Test'
            file_format.path = os.path.dirname(temp_file.name)
            file_format.file_name = os.path.basename(temp_file.name)
            file_format.file_type = 'csv'
            file_format.header = True
            file_format.separator = ','
            file_format.quote = '"'
            file_format.model = model_model

            file_format.fields = []
            for i, fieldname in enumerate(('module', 'model', 'name')):
                field = self.file_format_field()
                file_format.fields.append(field)
                field.name = fieldname
                field.sequence = i
                field.expression = '$%s' % fieldname
                if fieldname == 'name':
                    field.length = 15
                    field.fill_character = '-'
                    field.align = 'right'

            field = self.file_format_field()
            file_format.fields.append(field)
            field.name = 'N. fields'
            field.sequence = i + 1
            field.expression = 'len($fields)'
            field.number_format = '%.2f'
            field.decimal_character = ','

            field = self.file_format_field()
            file_format.fields.append(field)
            field.name = 'N. fields 2'
            field.sequence = i + 2
            field.expression = 'len($fields)'
            field.number_format = '%.2f'

            file_format.save()

            file_format.export_file([file_format_model.id])

            with open(temp_file.name) as output_file:
                file_content = output_file.read()

            self.assertEqual(file_content, (
                    '"module","model","name","N. fields","N. fields 2"\r\n'
                    '"file_format","file.format","----File Format","14,00",'
                    '"14.00"\r\n'))
            os.unlink(temp_file.name)

    def test0010export_xml_file(self):
        '''
        Test FileFormat.export_file.
        '''
        with Transaction().start(DB_NAME, USER, context=CONTEXT):
            model_model, = self.model.search([
                    ('model', '=', 'ir.model'),
                    ])
            file_format_model, = self.model.search([
                    ('model', '=', 'file.format'),
                    ])
            temp_file = tempfile.NamedTemporaryFile()
            temp_file.close()

            file_format = self.file_format()
            file_format.name = 'XML File Format Test'
            file_format.path = os.path.dirname(temp_file.name)
            file_format.file_name = os.path.basename(temp_file.name)
            file_format.file_type = 'xml'

            file_format.xml_format = """
                <?xml version="1.0" encoding="utf-8"?>
                <OpenShipments xmlns="x-schema:OpenShipments.xdr">
                    <OpenShipment ShipmentOption="" ProcessStatus="">
                        <ShipTo>
                            <CompanyOrName>Company TEST</CompanyOrName>
                        </ShipTo>
                        <ShipmentInformation>
                            <ServiceType>ST</ServiceType>
                            <NumberOfPackages>5</NumberOfPackages>
                        </ShipmentInformation>
                    </OpenShipment>
                </OpenShipments>
            """

            file_format.save()

            file_format.export_file([file_format_model.id])

            with open(temp_file.name) as output_file:
                file_content = output_file.read()

            self.assertEqual(file_content, """
                <?xml version="1.0" encoding="utf-8"?>
                <OpenShipments xmlns="x-schema:OpenShipments.xdr">
                    <OpenShipment ShipmentOption="" ProcessStatus="">
                        <ShipTo>
                            <CompanyOrName>Company TEST</CompanyOrName>
                        </ShipTo>
                        <ShipmentInformation>
                            <ServiceType>ST</ServiceType>
                            <NumberOfPackages>5</NumberOfPackages>
                        </ShipmentInformation>
                    </OpenShipment>
                </OpenShipments>
            """)
            os.unlink(temp_file.name)


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(
        unittest.TestLoader().loadTestsFromTestCase(FileFormatTestCase))
    return suite
