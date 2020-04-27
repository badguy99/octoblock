import appdaemon.plugins.hass.hassapi as hass
import requests
import json
import datetime
import dateutil.parser
import pytz


class OctoBlock(hass.Hass):
    def initialize(self):
        on00 = datetime.time(0, 0, 0)
        on30 = datetime.time(0, 30, 0)
        self.run_in(self.period_and_cost_callback, 5)
        self.run_hourly(self.period_and_cost_callback, on00)
        self.run_hourly(self.period_and_cost_callback, on30)

    def period_and_cost_callback(self, kwargs):
        self.hours = self.args.get('hour', 1)
        region = self.args.get('region', 'H')
        start_period = self.args.get('start_period', 'now')
        start_period = str(start_period).lower()
        limits = self.args.get('limits',  None)
        limit_start = None
        limit_end = None
        if limits:
            limit_start = limits.get('start_time', None)
            limit_end = limits.get('end_time', None)
        self.use_timezone = self.args.get('use_timezone', False)
        self.incoming = self.args.get('import', True)
        self.outgoing = self.args.get('export', False)

        if self.outgoing:
            # incoming defaults to True in case it hasnt been added to
            # apps.yaml as it wasnt an option when originally released
            # However if export is True, import must be False
            self.incoming = False
            if self.args.get('import') and self.args.get('export'):
                self.log('import and export should not both be True in the ' +
                         'same configuration block', level='ERROR')
        now = datetime.datetime.now()
        if start_period == 'today':
            if limit_end:
                try:
                    datetime.datetime.strptime(limit_end, "%H:%M")
                except ValueError:
                    self.log('end_time not in correct HH:MM format',
                             level='ERROR')

                limit_end_t = limit_end
                limit_end = (datetime.date.today().isoformat() + 'T' +
                             limit_end_t + ':00')
                if now.time() >= datetime.time(23, 30, 0):
                    limit_end = ((datetime.date.today() +
                                 datetime.timedelta(days=1)).isoformat() +
                                 'T' + limit_end_t + ':00')
            if limit_start:
                try:
                    datetime.datetime.strptime(limit_start, "%H:%M")
                except ValueError:
                    self.log('start_time not in correct HH:MM format',
                             level='ERROR')

                d = (datetime.date.today().isoformat() + 'T' +
                     limit_start + ':00')
                if now.time() >= datetime.time(23, 30, 0):
                    d = ((datetime.date.today() +
                         datetime.timedelta(days=1)).isoformat() +
                         'T' + limit_start + ':00')
            else:
                if now.time() < datetime.time(23, 30, 0):
                    d = datetime.date.today().isoformat() + 'T00:00:00'
                else:
                    d = ((datetime.date.today() +
                         datetime.timedelta(days=1)).isoformat() +
                         'T00:00:00')

        elif start_period == 'now':
            d = now.isoformat()
        else:
            self.log(
                'start_period in apps.yaml is not either "today" or "now",' +
                ' defaulting to "now"', level='WARNING')
            d = now.isoformat()

        self.get_period_and_cost(region, d, limit_end)

        hours = str(self.hours).replace(".", "_")
        if self.incoming:
            if self.hours == 0:
                self.set_state('sensor.octopus_current_price',
                               state=round(self.price, 4),
                               attributes={'unit_of_measurement': 'p/kWh',
                                           'icon': 'mdi:flash'})
            else:
                self.set_state('sensor.octopus_' + hours + 'hour_time',
                               state=self.time,
                               attributes={'icon': 'mdi:clock-outline'})
                self.set_state('sensor.octopus_' + hours + 'hour_price',
                               state=round(self.price, 4),
                               attributes={'unit_of_measurement': 'p/kWh',
                                           'icon': 'mdi:flash'})
        elif self.outgoing:
            if self.hours == 0:
                self.set_state('sensor.octopus_export_current_price',
                               state=round(self.price, 4),
                               attributes={'unit_of_measurement': 'p/kWh',
                                           'icon': 'mdi:flash-outline'})
            else:
                self.set_state('sensor.octopus_export_' + hours + 'hour_time',
                               state=self.time,
                               attributes={'icon': 'mdi:clock-outline'})
                self.set_state('sensor.octopus_export_' + hours + 'hour_price',
                               state=round(self.price, 4),
                               attributes={'unit_of_measurement': 'p/kWh',
                                           'icon': 'mdi:flash-outline'})

    def get_period_and_cost(self, region, timeperiod, timeperiodend):
        baseurl = 'https://api.octopus.energy/v1/products/'
        if self.incoming:
            if not timeperiodend:
                r = requests.get(
                    baseurl + 'AGILE-18-02-21/electricity-tariffs/' +
                    'E-1R-AGILE-18-02-21-' + str(region).upper() +
                    '/standard-unit-rates/?period_from=' + timeperiod)
            else:
                r = requests.get(
                    baseurl + 'AGILE-18-02-21/electricity-tariffs/' +
                    'E-1R-AGILE-18-02-21-' + str(region).upper() +
                    '/standard-unit-rates/?period_from=' + timeperiod +
                    '&period_to=' + timeperiodend)
        elif self.outgoing:
            if not timeperiodend:
                r = requests.get(
                    baseurl + 'AGILE-OUTGOING-19-05-13/electricity-tariffs/' +
                    'E-1R-AGILE-OUTGOING-19-05-13-' + str(region).upper() +
                    '/standard-unit-rates/?period_from=' + timeperiod)
            else:
                r = requests.get(
                    baseurl + 'AGILE-OUTGOING-19-05-13/electricity-tariffs/' +
                    'E-1R-AGILE-OUTGOING-19-05-13-' + str(region).upper() +
                    '/standard-unit-rates/?period_from=' + timeperiod +
                    '&period_to=' + timeperiodend)

        if r.status_code != 200:
            self.log('Error getting tariff data: {}'.format(r.text),
                     level='ERROR')

        tariff = json.loads(r.text)
        tariffresults = tariff[u'results']
        tariffresults.reverse()

        blocks = float(self.hours) * 2
        blocks = int(blocks)

        if self.hours == 0:
            if self.incoming:
                self.price = tariffresults[0]['value_inc_vat']
                self.log('Current import price is: {} p/kWh'.format(
                    self.price), level='INFO')
            elif self.outgoing:
                self.price = tariffresults[0]['value_inc_vat']
                self.log('Current export price is: {} p/kWh'.format(
                    self.price), level='INFO')
        else:
            for period in tariffresults:
                curridx = tariffresults.index(period)
                tr_len = len(tariffresults)
                if curridx > tr_len-blocks:
                    if self.incoming:
                        period[str(self.hours) + '_hour_average'] = 99
                    elif self.outgoing:
                        period[str(self.hours) + '_hour_average'] = 0
                    continue
                cost = 0
                for block in range(blocks):
                    cost = cost + (
                        tariffresults[curridx+block][u'value_inc_vat'])
                cost = cost / blocks
                period[str(self.hours) + '_hour_average'] = cost

            if self.incoming:
                self.price = min(
                    period[str(self.hours) + '_hour_average']
                    for period in tariffresults)
                self.log('Lowest average price for ' +
                         '{}'.format(str(self.hours)) +
                         ' hour block is: {} p/kWh'.format(self.price),
                         level='INFO')
            elif self.outgoing:
                self.price = max(
                    period[str(self.hours) + '_hour_average']
                    for period in tariffresults)
                self.log('Highest average price for ' +
                         '{}'.format(str(self.hours)) +
                         ' hour block is: {} p/kWh'.format(self.price),
                         level='INFO')

            for period in tariffresults:
                if period[str(self.hours) + '_hour_average'] == self.price:
                    self.time = period[u'valid_from']
                    if self.use_timezone:
                        fmt = '%Y-%m-%dT%H:%M:%S %Z'
                        greenwich = pytz.timezone('Europe/London')
                        date_time = dateutil.parser.parse(self.time)
                        local_datetime = date_time.astimezone(greenwich)
                        self.time = local_datetime.strftime(fmt)
                    self.log('Best priced {} hour '.format(str(self.hours)) +
                             'period starts at: {}'.format(self.time),
                             level='INFO')
