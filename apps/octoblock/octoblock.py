import appdaemon.plugins.hass.hassapi as hass
import requests
import json
import datetime
import dateutil.parser
import pytz


class OctoBlock(hass.Hass):
    def initialize(self):
        self.baseurl = 'https://api.octopus.energy/v1/products/'
        region = self.args.get('region', 'H')
        self.region = str(region).upper()
        self.use_timezone = self.args.get('use_timezone', False)
        self.blocks = self.args.get('blocks', None)
        self.lookaheads = self.args.get('lookaheads', None)

        on00 = datetime.time(0, 0, 0)
        on30 = datetime.time(0, 30, 0)
        self.run_in(self.period_and_cost_callback, 5)
        self.run_hourly(self.period_and_cost_callback, on00)
        self.run_hourly(self.period_and_cost_callback, on30)

    def period_and_cost_callback(self, kwargs):
        self.get_import_prices()

        if self.blocks:
            for block in self.blocks:
                self.hours = block.get('hour', 1)
                self.name = block.get('name', None)
                start_period = block.get('start_period', 'now')
                self.start_period = str(start_period).lower()
                self.incoming = block.get('import', True)
                self.outgoing = block.get('export', False)
                limits = block.get('limits',  None)
                if limits:
                    self.limit_start = limits.get('start_time', None)
                    self.limit_end = limits.get('end_time', None)

                if self.outgoing:
                    # incoming defaults to True in case it hasnt been added to
                    # apps.yaml as it wasnt an option when originally released
                    # However if export is True, import must be False
                    self.incoming = False
                    self.get_export_prices()
                    if block.get('import') and block.get('export'):
                        self.log('import and export should not both be True' +
                                 ' in the same configuration block',
                                 level='ERROR')

                self.log('Block: {}'.format(block), level='DEBUG')
                self.calculate_limit_points()
                self.get_period_and_cost()
                self.write_block_sensor_data()

        if self.lookaheads:
            for lookahead in self.lookaheads:
                self.price = lookahead.get('price')
                self.operation = lookahead.get('operation', 'below')
                if self.operation != 'below' and self.operation != 'above':
                    self.log('Operation must be either above or below',
                             level='ERROR')
                self.and_equal = lookahead.get('and_equal', False)
                self.duration_ahead = lookahead.get('duration_ahead', 12)
                self.name = lookahead.get('name', None)
                self.log('Lookahead:\nPrice: {}'.format(self.price) +
                         '\nFor: {}'.format(self.duration_ahead) +
                         '\nName: {}'.format(self.name), level='DEBUG')
                self.calculate_limit_points()
                self.write_lookahead_sensor_data()

    def get_import_prices(self):
        r = requests.get(
            self.baseurl + 'AGILE-18-02-21/electricity-tariffs/' +
            'E-1R-AGILE-18-02-21-' + self.region + '/standard-unit-rates/')

        if r.status_code != 200:
            self.log('Error {} getting incoming tariff data: {}'.format(
                     r.status_code, r.text), level='ERROR')

        tariff = json.loads(r.text)
        self.incoming_tariff = tariff[u'results']
        self.incoming_tariff.reverse()

    def get_export_prices(self):
        r = requests.get(
            self.baseurl + 'AGILE-OUTGOING-19-05-13/electricity-tariffs/' +
            'E-1R-AGILE-OUTGOING-19-05-13-' + self.region +
            '/standard-unit-rates/')

        if r.status_code != 200:
            self.log('Error {} getting outgoing tariff data: {}'.format(
                     r.status_code, r.text), level='ERROR')

        tariff = json.loads(r.text)
        self.outgoing_tariff = tariff[u'results']
        self.outgoing_tariff.reverse()

    def calculate_limit_points(self):
        now = datetime.datetime.now()
        self.start_date = None
        self.end_date = None
        if self.start_period == 'today':
            if hasattr(self, 'limit_end'):
                try:
                    datetime.datetime.strptime(self.limit_end, "%H:%M")
                except ValueError:
                    self.log('end_time not in correct HH:MM format',
                             level='ERROR')

                limit_end_t = self.limit_end
                self.end_date = (datetime.date.today().isoformat() + 'T' +
                                  limit_end_t + ':00Z')
                if now.time() >= datetime.time(23, 30, 0):
                    self.end_date = ((datetime.date.today() +
                                     datetime.timedelta(days=1)).isoformat() +
                                     'T' + limit_end_t + ':00Z')
            if hasattr(self, 'limit_start'):
                try:
                    datetime.datetime.strptime(self.limit_start, "%H:%M")
                except ValueError:
                    self.log('start_time not in correct HH:MM format',
                             level='ERROR')

                self.start_date = (datetime.date.today().isoformat() + 'T' +
                                   self.limit_start + ':00Z')
                if now.time() >= datetime.time(23, 30, 0):
                    self.start_date = ((datetime.date.today() +
                                       datetime.timedelta(days=1)).isoformat()
                                       + 'T' + self.limit_start + ':00Z')
            else:
                if now.time() < datetime.time(23, 30, 0):
                    self.start_date = (datetime.date.today().isoformat() +
                                       'T00:00:00Z')
                else:
                    self.start_date = ((datetime.date.today() +
                         datetime.timedelta(days=1)).isoformat() +
                         'T00:00:00Z')

        elif self.start_period == 'now':
            flr_now = self.floor_dt(now)
            self.start_date = flr_now.isoformat(timespec='seconds') + 'Z'
        else:
            self.log(
                'start_period in apps.yaml is not either "today" or "now",' +
                ' defaulting to "now"', level='WARNING')
            self.start_date = now.isoformat()
        self.log('start date: {} / end date: {}'.format(
                 self.start_date, self.end_date), level='DEBUG')

    def floor_dt(self, dt, interval=30):
        replace = (dt.minute // interval)*interval
        newdt = dt.replace(minute = replace, second=0, microsecond=0)
        return newdt

    def dt_to_api_date(self, dt):
        return dt.isoformat() + 'Z'

    def date_to_idx(self, tariff, date):
        # Date format for API - 2020-05-29T20:00:00Z
        idx = next((i for i, item in enumerate(tariff) if item['valid_from'] == date), None)
        return idx

    def get_period_and_cost(self):
        blocks = float(self.hours) * 2
        blocks = int(blocks)
        if self.incoming:
            tariffresults = self.incoming_tariff
        else:
            tariffresults = self.outgoing_tariff

        if self.hours == 0:
            now_utc_flr = self.floor_dt(datetime.datetime.utcnow())
            api_date_now = self.dt_to_api_date(now_utc_flr)
            i = self.date_to_idx(tariffresults, api_date_now)
            if self.incoming:
                self.price = tariffresults[i]['value_inc_vat']
                self.log('Current import price is: {} p/kWh'.format(
                    self.price), level='INFO')
            elif self.outgoing:
                self.price = tariffresults[i]['value_inc_vat']
                self.log('Current export price is: {} p/kWh'.format(
                    self.price), level='INFO')
        else:
            start_idx = self.date_to_idx(tariffresults, self.start_date)
            end_idx = self.date_to_idx(tariffresults, self.end_date)
            if not end_idx:
                end_idx = len(tariffresults) - 1
            for curridx in range (start_idx, end_idx):
                period = tariffresults[curridx]
                tr_len = len(tariffresults)
                if curridx > tr_len - blocks:
                    if self.incoming:
                        period[str(self.hours) + '_hour_average'] = 99
                    elif self.outgoing:
                        period[str(self.hours) + '_hour_average'] = 0
                    continue
                cost = 0
                for block in range(blocks):
                    cost = cost + (
                        tariffresults[curridx + block][u'value_inc_vat'])
                cost = cost / blocks
                period[str(self.hours) + '_hour_average'] = cost

            if self.incoming:
                self.price = min(
                    tariffresults[curridx][str(self.hours) + '_hour_average']
                    for curridx in range (start_idx, end_idx))
                self.log('Lowest average price for ' +
                         '{}'.format(str(self.hours)) +
                         ' hour block is: {} p/kWh'.format(self.price),
                         level='INFO')
            elif self.outgoing:
                self.price = max(
                    tariffresults[curridx][str(self.hours) + '_hour_average']
                    for curridx in range (start_idx, end_idx))
                self.log('Highest average price for ' +
                         '{}'.format(str(self.hours)) +
                         ' hour block is: {} p/kWh'.format(self.price),
                         level='INFO')

            for curridx in range (start_idx, end_idx):
                period = tariffresults[curridx]
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

    def write_block_sensor_data(self):
        hours = str(self.hours).replace(".", "_")

        if self.name:
            name = str(self.name).replace(".", "_")
            entity_id_t = 'sensor.' + name + '_time'
            entity_id_p = 'sensor.' + name + '_price'

        if self.incoming:
            if self.hours == 0:
                self.set_state('sensor.octopus_current_price',
                               state=round(self.price, 4),
                               attributes={'unit_of_measurement': 'p/kWh',
                                           'icon': 'mdi:flash'})
            else:
                if not self.name:
                    entity_id_t = 'sensor.octopus_' + hours + 'hour_time'
                    entity_id_p = 'sensor.octopus_' + hours + 'hour_price'

                self.set_state(entity_id_t,
                               state=self.time,
                               attributes={'icon': 'mdi:clock-outline'})
                self.set_state(entity_id_p,
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
                if not self.name:
                    entity_id_t = 'sensor.octopus_export' + hours + 'hour_time'
                    entity_id_p = 'sensor.octopus_export' + hours + 'hour_price'

                self.set_state(entity_id_t,
                               state=self.time,
                               attributes={'icon': 'mdi:clock-outline'})
                self.set_state(entity_id_p,
                               state=round(self.price, 4),
                               attributes={'unit_of_measurement': 'p/kWh',
                                           'icon': 'mdi:flash-outline'})

    def is_price_below_x(self):
        '''
        HA sensor that will be set to true if the price will go below
        or above (depending upon operation setting) a specified point, x,
        within the next y hours, up to the maximum look ahead that Octopus
        Energy provide price data for.
        '''
        result = False
        tariffresults = self.incoming_tariff
        now_utc_flr = self.floor_dt(datetime.datetime.utcnow())
        api_date_now = self.dt_to_api_date(now_utc_flr)
        i = self.date_to_idx(tariffresults, api_date_now)

        for n in range (i, self.duration_ahead*2+i):
            period_cost = tariffresults[n]['value_inc_vat']
            if period_cost:
                if self.operation == 'below':
                    if period_cost < self.price:
                        result = True
                if self.operation == 'above':
                    if period_cost > self.price:
                        result = True
                if self.and_equal:
                    if period_cost == self.price:
                        result = True
        return result

    def write_lookahead_sensor_data(self):
        state=self.is_price_below_x()
        if self.name:
            name = str(self.name).replace(".", "_")
            self.entity_id = 'sensor.' + name
        else:
            price = str(self.price).replace(".", "_")
            duration_ahead = str(self.duration_ahead).replace(".", "_")
            self.entity_id = 'sensor.lookahead_for_cost_' + self.operation + \
                             '_' + price + '_for_' + duration_ahead + '_hours'

        self.set_state(self.entity_id,
                       state=state,
                       attributes={'icon': 'mdi:binoculars'})
