# octoblock
Octoblock is an app which works under [AppDaemon](https://www.home-assistant.io/docs/ecosystem/appdaemon/) within [Home Assistant](https://www.home-assistant.io/) which finds the cheapest “n” hour block and works out the price of that block, for the Octopus Energy, Agile Octopus tariff. It creates and sets sensors for the cost and start time,  for example, using the apps.yaml file below, the following entities are created and then updated:
```
sensor.octopus_1hour_time
sensor.octopus_1hour_cost
sensor.octopus_1_5hour_time
sensor.octopus_1_5hour_cost
```

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)

### Installation

Use [HACS](https://github.com/custom-components/hacs) or download the octoblock directory from inside the apps directory [here](https://github.com/badguy99/octoblock/releases) to your local apps directory, then add the configuration to enable the octoblock module.

### Apps.yaml Configuration
```yaml
octo_block_1hour:
  module: octoblock
  class: OctoBlock
  region: H
  hour: 1

octo_block_90minutes:
  module: octoblock
  class: OctoBlock
  region: H
  hour: 1.5
  ```
The module and class sections need to remain as above, but the title, and number of hours can be set as you like, and you can have multiple blocks with different time periods as needed. It will work with whole hour or halve hour blocks in the `hour` setting.
`region` is the region letter from the end of `E-1R-AGILE-18-02-21-H` which can be found on the `https://octopus.energy/dashboard/developer/` webpage in the Unit Rates section for your account.
