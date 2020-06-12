# octoblock
Octoblock is an app which works under [AppDaemon](https://www.home-assistant.io/docs/ecosystem/appdaemon/) within [Home Assistant](https://www.home-assistant.io/) which finds the cheapest “n” hour block for import or the most expensive “n” hour block for export, and works out the price of that block, for the Octopus Energy, Agile Octopus / Agile Outgoing Octopus tariffs. 

*Please note:* *Breaking Changes!* New yaml structure in version 2!

It creates and sets sensors for the cost and start time,  for example, using the `apps.yaml` file below, the following entities are created and then updated:
```yaml
sensor.octopus_1hour_time
sensor.octopus_1hour_price
sensor.octopus_1_5hour_time
sensor.octopus_1_5hour_price
```

Sensors for export will be created with naming such as:
```yaml
sensor.octopus_export_1hour_time
sensor.octopus_export_1hour_price
```

With `start_period` set to `now` and `hour` set to `0` the current import or export price is returned, and the sensors are named:
```yaml
sensor.octopus_current_price
sensor.octopus_export_current_price
```

Sensor names can be overridden and your own name specified in the yaml configuration. These will be of the format `sensor.<your_name>_time` and `sensor.<your_name>_price` with any dots in `<your_name>` changed to underscores.

[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/custom-components/hacs)

## Installation

Use [HACS](https://github.com/custom-components/hacs) or download the octoblock directory from inside the apps directory [here](https://github.com/badguy99/octoblock/releases) to your local apps directory, then add the configuration to enable the octoblock module.

## apps.yaml Configuration
```yaml
octoblock:
  module: octoblock
  class: OctoBlock
  region: H
  use_timezone: False
  blocks:
    - hour: 1
      import: True
      start_period: now
      name: octopus_1hour
    - hour: 1.5
      start_period: today
      name: octopus_vacuum
      limits:
        start_time: '07:00'
        end_time: '16:00'
    - hour: 2
      import: True
      start_period: now
    - hour: 0
      start_period: now
      name: octopus_current_import
    - hour: 0
      export: True
      import: False
      start_period: now
      name: octopus_current_export
  lookaheads:
    - price: 3.0
      operation: below
      and_equal: True
      duration_ahead: 12
      name: hw_via_electric_not_gas
```

The module and class sections need to remain as above, other sections should be changed as required.

### Blocks

You can have multiple blocks with different time periods (`hour` setting) or starting points (`start_period` setting) as needed. It will work with whole hour or half hour blocks in the `hour` setting.

`region` is the region letter from the end of `E-1R-AGILE-18-02-21-H` which can be found on the [Octopus Energy developer dashboard](https://octopus.energy/dashboard/developer/) webpage in the Unit Rates section for your account.

`start_period` is optional, it can be set to either `now` or `today`, and will default to `now`

`now` and `today` give subtly different results. `now` is re-evaluated every time the callback is run (once every 30 minutes), and `today` uses a start time of 00:00:00 with today's date.

This means that using `today` you will get the absolute cheapest block for today, even if that is in the past, and using `now` will get the cheapest block for the remainder of the day. `today` may be of more use with automated triggers, and `now` may be of use when you are wanting to display the cheapest time on a Lovelace UI card and use that information to turn on devices which cannot be automated, by hand.

This may be best illustrated with a couple of pictures:

![State information with now start period](https://github.com/badguy99/octoblock/blob/master/StartTimeNow.PNG)

Using `now` `start_period` this has turned on and off a few times within the day as it is reevaluated as the day goes on

![State information with today start period](https://github.com/badguy99/octoblock/blob/master/StartTimeToday.PNG)

Using `today` `start_period` this has only turned on once during the day

Setting `start_period` to `now` and `hours` to `0` will give the current import or export price.

When using `today` for the `start_period` it can be limited further usings `limits > start_time` and/or `limits > end_time` (please note the formating in the example yaml above) to restrict the period searched. This may be useful for example if you have something that you only want to run within certain times of the day, due to noise issues etc.

`use_timezone` can be set to True or False, and defaults to False, it allows you to specify if the date/time should be displayed in UTC (False), or using Europe/London (True) as the timezone. For example, `2020-03-29T02:00:00Z` or `2020-03-29T03:00:00 BST` respectively.

`import` and `export` should be set to True or False as required, `import: True` and `export: False` for the Agile Octopus tariff, and `import: False` and `export: True` for the Agile Outgoing Octopus tariff.

### Lookaheads

Look aheads provide a HA sensor that will be set to true if the price will go below or above (depending upon operation setting) a specified point, x, within the next `duration_ahead` hours, up to the maximum look ahead that Octopus Energy provide price data for.

Setting `operation` to `above` or `below` and `and_equal` to `True` or `False` in the yaml file give different functions; namely: greater than, less than, greater than & equal, and less than and equal. Such that it should be possible to set up required trigger points looking at prices in the future for automations.

## Home Assistant Automation

The created start time sensors can then be used to trigger automations within Home Assistant.
This requires the [Time Date integration](https://www.home-assistant.io/integrations/time_date/) to be configured as well. The triggers such as the following can be set up to trigger the automations.

```yaml
trigger:
  platform: template
  value_template: >
  {% if (states("sensor.date_time_iso") + "Z") == (states("sensor.octopus_1hour_time")) %}
    true
  {% endif %}
```
  
## Lovelace UI Cards

Once the sensors are created, they can be displayed as cards within the Lovelace UI. For example:

```yaml
type: entities
title: Best 1hr Price
show_header_toggle: false
entities:
  - entity: sensor.octopus_1hour_price
    icon: 'mdi:flash'
    name: Price (p/kWh)
  - entity: sensor.octopus_1hour_time
    icon: 'mdi:clock-outline'
    name: Time
        
type: entities
title: Best 1.5hr Price
show_header_toggle: false
entities:
  - entity: sensor.octopus_1_5hour_price
    icon: 'mdi:flash'
    name: Price (p/kWh)
  - entity: sensor.octopus_1_5hour_time
    icon: 'mdi:clock-outline'
    name: Time
```

![Lovelace UI best usage time example cards](https://github.com/badguy99/octoblock/blob/master/LovelaceBesttimeCard.PNG)
