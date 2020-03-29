import appdaemon.plugins.hass.hassapi as hass
import requests
import json
import datetime
import dateutil.parser
import pytz


class OctoBlock(hass.Hass):
    def initialize(self):
        time = datetime.datetime.now()
        time = time + datetime.timedelta(seconds=5)
        self.run_every(self.period_and_cost_callback, time, 30 * 60)

    def period_and_cost_callback(self, kwargs):
        self.hours = self.args.get('hour', 1)
        region = self.args.get('region', 'H')
        start_period = self.args.get('start_period', 'now')
        start_period = str(start_period).lower()
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
        if start_period == 'today':
            d = datetime.date.today().isoformat() + 'T00:00:00'
        elif start_period == 'now':
            d = datetime.datetime.now().isoformat()
        else:
            self.log(
                'start_period in apps.yaml is not either "today" or "now",' +
                ' defaulting to "now"')
            d = datetime.datetime.now().isoformat()

        self.get_period_and_cost(region, d)

        hours = str(self.hours).replace(".", "_")
        if self.incoming:
            self.set_state('sensor.octopus_' + hours + 'hour_time',
                           state=self.time,
                           attributes={'icon': 'mdi:clock-outline'})
            self.set_state('sensor.octopus_' + hours + 'hour_price',
                           state=round(self.price, 4),
                           attributes={'unit_of_measurement': 'p/kWh',
                                       'icon': 'mdi:flash'})
        elif self.outgoing:
            self.set_state('sensor.octopus_export_' + hours + 'hour_time',
                           state=self.time,
                           attributes={'icon': 'mdi:clock-outline'})
            self.set_state('sensor.octopus_export_' + hours + 'hour_price',
                           state=round(self.price, 4),
                           attributes={'unit_of_measurement': 'p/kWh',
                                       'icon': 'mdi:flash-outline'})

    def get_period_and_cost(self, region, timeperiod):
        baseurl = 'https://api.octopus.energy/v1/products/'
        if self.incoming:
            r = requests.get(
                baseurl + 'AGILE-18-02-21/electricity-tariffs/' +
                'E-1R-AGILE-18-02-21-' + str(region).upper() +
                '/standard-unit-rates/?period_from=' + timeperiod)
        elif self.outgoing:
            r = requests.get(
                baseurl + 'AGILE-OUTGOING-19-05-13/electricity-tariffs/' +
                'E-1R-AGILE-OUTGOING-19-05-13-' + str(region).upper() +
                '/standard-unit-rates/?period_from=' + timeperiod)

        tariff = json.loads(r.text)
        tariffresults = tariff[u'results']
        tariffresults.reverse()

        blocks = float(self.hours) * 2
        blocks = int(blocks)

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
                cost = cost + (tariffresults[curridx+block][u'value_inc_vat'])
            cost = cost / blocks
            period[str(self.hours) + '_hour_average'] = cost

        if self.incoming:
            self.price = min(
                period[str(self.hours) + '_hour_average']
                for period in tariffresults)
            self.log('Lowest average price for {}'.format(str(self.hours)) +
                     ' hour block is: {} p/kWh'.format(self.price))
        elif self.outgoing:
            self.price = max(
                period[str(self.hours) + '_hour_average']
                for period in tariffresults)
            self.log('Highest average price for {}'.format(str(self.hours)) +
                     ' hour block is: {} p/kWh'.format(self.price))

        for period in tariffresults:
            if period[str(self.hours) + '_hour_average'] == self.price:
                self.time = period[u'valid_from']
                if self.use_timezone:
                    fmt = '%Y-%m-%dT%H:%M:%S %Z'
                    greenwich = pytz.timezone('Europe/London')
                    date_time = dateutil.parser.parse(self.time)
                    local_datetime = date_time.astimezone(greenwich)
                    self.time = local_datetime.strftime(fmt)
                self.log('Best priced {} hour period'.format(str(self.hours)) +
                         ' starts at: {}'.format(self.time))
