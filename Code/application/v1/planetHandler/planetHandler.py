from application.v1.baseHandler.baseHandler import BaseHandler
from math import ceil
from datetime import datetime
import services.base_exception as base_exception

# Swapi
import services.swapi as swapi

# Mongodb
import services.mongodb as mongo


class PlanetHandler(BaseHandler):

    def prepare(self):

        try:
            super(PlanetHandler, self).prepare()

            # mongo
            self.mongodb = mongo.mongoDB(
                self.server_config['mongodb']['host'],
                int(self.server_config['mongodb']['port']),
                self.server_config['mongodb']['database'],
                self.server_config['mongodb']['colletion']
            )
            self.mongodb.check_status()

        except base_exception.BaseExceptionError as e:
            self.send_base_error_exception(e.error)
        except Exception as e:
            self.send_base_error_exception('internal_error', e)

    def get(self):

        self.request.log._info('GET Invoice')
        try:
            where = ""
            total_npage = ""
            result = dict()
            qparams = list()

            if 'id_invoice' in self.fields.keys() and self.fields['id_invoice'].isdigit():
                where += 'AND id_invoice = %s '
                qparams.append(self.fields['id_invoice'])

            if 'Document' in self.fields.keys() and self.fields['Document']:
                where += 'AND UPPER(Document) = UPPER(%s) '
                qparams.append(self.fields['Document'])

            if 'ReferenceMonth' in self.fields.keys() and self.fields['ReferenceMonth'] and \
                    self.fields['ReferenceMonth'].isdigit():
                where += "AND ReferenceMonth = %s "
                qparams.append(self.fields['ReferenceMonth'])

            if 'ReferenceYear' in self.fields.keys() and self.fields['ReferenceYear'] and \
                    self.fields['ReferenceYear'].isdigit():
                where += "AND ReferenceYear = %s "
                qparams.append(self.fields['ReferenceYear'])

            select = """SELECT 
                                id_invoice,
                                Amount,
                                Document,
                                Description,
                                ReferenceMonth,
                                ReferenceYear,
                                CreatedAt
                            FROM invoices 
                            WHERE isActive = 1 
                          """
            if where:
                select += where
            cursor = self.db.cursor()

            if 'orderby' in self.fields.keys() and self.fields['orderby']:
                try:
                    orderby = list()
                    for i in self.fields['orderby'].split(','):
                        if i.strip() in ['Document', 'ReferenceMonth', 'ReferenceYear']:
                            orderby.append(i.strip())
                    select += 'ORDER BY %s '
                    qparams.append(", ".join(orderby))
                except:
                    pass

            if 'ResultByPage' in self.fields.keys() and self.fields['ResultByPage'] and \
                    self.fields['ResultByPage'].isdigit() and 'npage' in self.fields.keys() and \
                    self.fields['npage'] and self.fields['npage'].isdigit():

                # Get total
                try:
                    cursor.execute(select, params=qparams)
                    cursor.fetchall()
                    total_npage = cursor.rowcount
                except mysql.connector.InterfaceError as e:
                    base_exception.send_base_error_internal(e)

                select += "LIMIT %s, %s;"
                qparams.append(int(self.fields['npage']) * int(self.fields['ResultByPage'])\
                               - int(self.fields['ResultByPage']))
                qparams.append(int(self.fields['ResultByPage']))

                result.update(
                    qtd_pages=ceil(int(total_npage) / int(self.fields['ResultByPage'])),
                    page=int(self.fields['npage']) if total_npage else 0
                )
            try:
                cursor.execute(select, params=qparams)
                rows = cursor.fetchall()
                qtd_total = cursor.rowcount
                result.update(total=total_npage if total_npage else qtd_total)

                columns = [column[0] for column in cursor.description]
                results_mysql = []

                for row in rows:
                    results_mysql.append(dict((zip(columns, row))))
            except mysql.connector.InterfaceError as e:
                BaseExceptionError.send_base_error_internal(e)

            list_results = list()
            for row in results_mysql:
                for i in row:
                    row[i] = self.utils.to_json_able(row[i])
                list_results.append(row)

            result.update(result=list_results)
            cursor.close()
            self.finish(result)

        except base_exception.BaseExceptionError as e:
            self.send_base_error_exception(e.error)
        except Exception as e:
            self.send_base_error_exception(e, 'internal_error')

    def post(self):

        self.request.log._info('POST Planet')
        try:
            q_params = list()

            if ('name' not in self.fields.keys() or not self.fields['name'])\
                or ('climate' not in self.fields.keys() or not\
                self.fields['climate']) or\
                ('terrain' not in self.fields.keys() or not\
                self.fields['terrain']):
                raise base_exception.BaseExceptionError('missing_fields')

            # check qtd_films
            ext_swapi = swapi.Swapi(
                '%s%s' % (
                    self.server_config['swapi']['url'],
                    self.fields['name']
                ),
                self.redis_db_swapi,
                self.server_config['grant']['swapi_expire']
            )
            qtd_films = ext_swapi.get_qtd_planet_by_name()
            data = dict(
                name=self.fields['name'],
                climate=self.fields['climate'],
                terrain=self.fields['terrain'],
                qtd_films=self.fields['qtd_films'] if 'qtd_films' in\
                    self.fields and self.fields['qtd_films'] else qtd_films
            )
            id_planet = self.mongodb.planet_save(data)

            self.finish(
                dict(id=id_planet.__str__())
            )

        except base_exception.BaseExceptionError as e:
            self.send_base_error_exception(e.error)
        except Exception as e:
            self.send_base_error_exception('internal_error', e)

    def delete(self):

        self.request.log._info('DELETE Invoice')
        try:
            if 'id_invoice' not in self.fields.keys() or not self.fields['id_invoice'] or not self.fields['id_invoice'].isdigit():
                raise self.utils.BaseExceptionError('invalid_fields', 'id_invoice')

            select = "SELECT id_invoice FROM invoices WHERE isActive = 1 AND id_invoice = %s;"
            cursor = self.db.cursor()
            try:
                cursor.execute(select, params=[self.fields['id_invoice']])
                row = cursor.fetchone()
            except mysql.connector.InterfaceError as e:
                self.send_base_error_internal(e)
            if not row:
                raise self.utils.BaseExceptionError('not_found', 'Invoice Not Found')

            update = """UPDATE invoices SET 
                        isActive = %s,
                        DeactiveAt = %s
                      WHERE id_invoice = %s;"""

            try:
                cursor.execute(update, params=[0, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), self.fields['id_invoice']])
            except mysql.connector.InterfaceError as e:
                self.send_base_error_internal(e)

            self.db.commit()
            cursor.close()
            self.finish(dict())
        except self.utils.BaseExceptionError as e:
            self.send_base_error_exception(e.error, e.description)
        except Exception as e:
            self.send_base_error_internal(e)
