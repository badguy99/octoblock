# octoblock
Octoblock is an app which works under [AppDaemon](https://www.home-assistant.io/docs/ecosystem/appdaemon/) within [Home Assistant](https://www.home-assistant.io/) which finds the cheapest “n” hour block and works out the price of that block, for the Octopus Energy, Agile Octopus tariff. It creates and sets sensors for the cost and start time,  for example, using the apps.yaml file below, the following entities are created and then updated:
```
sensor.octopus_1hour_time
sensor.octopus_1hour_cost
sensor.octopus_1_5hour_time
sensor.octopus_1_5hour_cost
```

[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/custom-components/hacs)

### Installation

Use [HACS](https://github.com/custom-components/hacs) or download the octoblock directory from inside the apps directory [here](https://github.com/badguy99/octoblock/releases) to your local apps directory, then add the configuration to enable the octoblock module.

### Apps.yaml Configuration
```yaml
octo_block_1hour:
  module: octoblock
  class: OctoBlock
  region: H
  hour: 1
  use_timezone: False

octo_block_90minutes:
  module: octoblock
  class: OctoBlock
  region: H
  hour: 1.5
  start_period: now
  use_timezone: True
  ```
The module and class sections need to remain as above, other sections should be changed as required.

| Field        | Changeable | Example          |
| -----        | ---------- | -------          |
| Title        | Yes        | octo_block_1hour |
| module       | No         | octoblock        |
| class        | No         | OctoBlock        |
| region       | Yes        | H                |
| hour         | Yes        | 1                |
| start_period | Yes        | today            |
| use_timezone | Yes        | True             |

You can have multiple blocks with different time periods (`hour` setting) or starting points (`start_period` setting) as needed. It will work with whole hour or half hour blocks in the `hour` setting.

`region` is the region letter from the end of `E-1R-AGILE-18-02-21-H` which can be found on the [Octopus Energy developer dashboard](https://octopus.energy/dashboard/developer/) webpage in the Unit Rates section for your account.

`start_period` is optional, it can be set to either `now` or `today`, and will default to `now`

`now` and `today` give subtly different results. `now` is reevaluated ever time the callback is run (once every 30 minutes), and `today` uses a start time of 00:00:00 with today's date.

This means that using `today` you will get the absolute cheapest block for today, even if that is in the past, and using `now` will get the cheapest block for the remainder of the day. `today` may be of more use with automated triggers, and `now` may be of use when you are wanting to display the cheapest time on a Lovelace UI card and use that information to turn on devices which cannot be automated, by hand.

This may be best illustrated with a couple of pictures:

![State information with now start period](https://github.com/badguy99/octoblock/blob/master/StartTimeNow.PNG)

Using `now` start_period this has turned on and off a few times within the day as it is reevaluated as the day goes on

![State information with today start period](https://github.com/badguy99/octoblock/blob/master/StartTimeToday.PNG)

Using `today` start_period this has only turned on once during the day

`use_timezone` can be set to True or False, and defaults to False, it allows you to specify if the date/time should be displayed in UTC (False), or using Europe/London (True) as the timezone. For example, `2020-03-29T02:00:00Z` or `2020-03-29T03:00:00 BST` respectively.

### Home Assistant Automation

The created start time sensors can then be used to trigger automations within Home Assistant.
This requires the [Time Date integration](https://www.home-assistant.io/integrations/time_date/) to be configured as well. The triggers such as the following can be set up to trigger the automations.

```
trigger:
  platform: template
  value_template: >
  {% if (states("sensor.date_time_iso") + "Z") == (states("sensor.octopus_1hour_time")) %}
    true
  {% endif %}
```
  
### Lovelace UI Cards

Once the sensors are created, they can be displayed as cards within the Lovelace UI. For example:

```
      - entities:
          - entity: sensor.octopus_1hour_price
            icon: 'mdi:flash'
            name: Price (p/kWh)
          - entity: sensor.octopus_1hour_time
            icon: 'mdi:clock-outline'
            name: Time
        show_header_toggle: false
        title: Best 1hr Price
        type: entities
      - entities:
          - entity: sensor.octopus_1_5hour_price
            icon: 'mdi:flash'
            name: Price (p/kWh)
          - entity: sensor.octopus_1_5hour_time
            icon: 'mdi:clock-outline'
            name: Time
        show_header_toggle: false
        title: Best 1.5hr Price
        type: entities
```
![Lovelace UI best usage time example cards](https://github.com/badguy99/octoblock/blob/master/LovelaceBesttimeCard.PNG)
