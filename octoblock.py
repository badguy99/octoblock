import appdaemon.plugins.hass.hassapi as hass
import requests
import json
import datetime

class OctoBlock(hass.Hass):
    def initialize(self):
        time = datetime.datetime.now()
        time = time + datetime.timedelta(seconds=5)
        self.run_every(self.get_best_period_and_cost, time, 30 * 60)

    def get_best_period_and_cost(self, kwargs):
        hours = self.args['hour']
        d = datetime.datetime.now().isoformat()
        r = requests.get('https://api.octopus.energy/v1/products/AGILE-18-02-21/electricity-tariffs/E-1R-AGILE-18-02-21-H/standard-unit-rates/?period_from=' + d)

        tariff = json.loads(r.text)
        tariffresults = tariff[u'results']
        tariffresults.reverse()

        blocks = float(hours) * 2
        blocks = int(blocks)

        for period in tariffresults:
            curridx = tariffresults.index(period)
            l = len(tariffresults)
            if curridx > l-blocks:
                period[str(hours) + '_hour_average'] = 99
                continue
            cost = 0
            for block in range(blocks):
                cost = cost + (tariffresults[curridx+block][u'value_inc_vat'])
            cost = cost / blocks
            period[str(hours) + '_hour_average'] = cost

        self.minprice = min(period[str(hours) + '_hour_average'] for period in tariffresults)
        self.log('Lowest average price for a {} hour block is: {} p/kWh'.format(str(hours), self.minprice))

        for period in tariffresults:
            if period[str(hours) + '_hour_average'] == self.minprice:
                self.time = period[u'valid_from']
                self.log('Lowest priced {} hour period starts at: {}'.format(str(hours), self.time))

        hours = str(hours).replace(".", "_")
        self.set_state('sensor.octopus_' + hours + 'hour_time', state = self.time)
        self.set_state('sensor.octopus_' + hours + 'hour_price', state = round(self.minprice,4))
