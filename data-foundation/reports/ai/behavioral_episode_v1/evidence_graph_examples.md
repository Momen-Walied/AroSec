# Evidence Graph Examples (analysis only)

## episode:cceca8f99e4a9b1a89e5 (STRONG)
- assets: ['asset:unsw:192.168.1.1', 'asset:unsw:192.168.1.240', 'asset:unsw:208.67.220.220', 'asset:unsw:8.8.8.8']
- relationships: ['rel:asset:unsw:192.168.1.240|asset:unsw:192.168.1.1|COMMUNICATES_WITH', 'rel:asset:unsw:192.168.1.240|asset:unsw:208.67.220.220|COMMUNICATES_WITH', 'rel:asset:unsw:192.168.1.240|asset:unsw:8.8.8.8|COMMUNICATES_WITH']
- evidence families: ['TOPOLOGY_SPREAD', 'PROTOCOL_CHANGE', 'PORT_CHANGE', 'TRAFFIC_VOLUME', 'DIRECTIONAL_CHANGE']
  - edge ['asset:unsw:192.168.1.1', 'asset:unsw:192.168.1.240'] score=0.34270891109260954 reasons=['FAN_OUT_DEVIATION', 'PROTOCOL_NOVELTY', 'TRAFFIC_VOLUME_DEVIATION']
  - edge ['asset:unsw:192.168.1.240', 'asset:unsw:208.67.220.220'] score=0.3201727666264798 reasons=['FAN_OUT_DEVIATION', 'TRAFFIC_VOLUME_DEVIATION']
  - edge ['asset:unsw:192.168.1.240', 'asset:unsw:208.67.220.220'] score=0.31964795057412837 reasons=['FAN_OUT_DEVIATION', 'TRAFFIC_VOLUME_DEVIATION']
  - edge ['asset:unsw:192.168.1.240', 'asset:unsw:208.67.220.220'] score=0.3193003528481923 reasons=['FAN_OUT_DEVIATION', 'TRAFFIC_VOLUME_DEVIATION']
  - edge ['asset:unsw:192.168.1.240', 'asset:unsw:208.67.220.220'] score=0.3193003528481923 reasons=['FAN_OUT_DEVIATION', 'TRAFFIC_VOLUME_DEVIATION']
  - edge ['asset:unsw:192.168.1.240', 'asset:unsw:208.67.220.220'] score=0.32166774576499335 reasons=['FAN_OUT_DEVIATION', 'TRAFFIC_VOLUME_DEVIATION']
  - edge ['asset:unsw:192.168.1.240', 'asset:unsw:208.67.220.220'] score=0.3200831960530656 reasons=['FAN_OUT_DEVIATION', 'TRAFFIC_VOLUME_DEVIATION']
  - edge ['asset:unsw:192.168.1.240', 'asset:unsw:8.8.8.8'] score=0.3232547539969599 reasons=['FAN_OUT_DEVIATION', 'TRAFFIC_VOLUME_DEVIATION']

## episode:2f13ac7b2020ba4bc6e6 (STRONG)
- assets: ['asset:unsw:192.168.1.240', 'asset:unsw:208.67.220.220', 'asset:unsw:8.8.8.8']
- relationships: ['rel:asset:unsw:192.168.1.240|asset:unsw:208.67.220.220|COMMUNICATES_WITH', 'rel:asset:unsw:192.168.1.240|asset:unsw:8.8.8.8|COMMUNICATES_WITH']
- evidence families: ['PEER_NOVELTY', 'TOPOLOGY_SPREAD', 'PROTOCOL_CHANGE', 'PORT_CHANGE', 'TRAFFIC_VOLUME', 'DIRECTIONAL_CHANGE', 'PEER_SET_CHANGE']
  - edge ['asset:unsw:192.168.1.240', 'asset:unsw:208.67.220.220'] score=0.3193899334426527 reasons=['FAN_OUT_DEVIATION', 'TRAFFIC_VOLUME_DEVIATION']
  - edge ['asset:unsw:192.168.1.240', 'asset:unsw:208.67.220.220'] score=0.31982795916859114 reasons=['FAN_OUT_DEVIATION', 'TRAFFIC_VOLUME_DEVIATION']
  - edge ['asset:unsw:192.168.1.240', 'asset:unsw:208.67.220.220'] score=0.3201727666264798 reasons=['FAN_OUT_DEVIATION', 'TRAFFIC_VOLUME_DEVIATION']
  - edge ['asset:unsw:192.168.1.240', 'asset:unsw:208.67.220.220'] score=0.32165771681437244 reasons=['FAN_OUT_DEVIATION', 'TRAFFIC_VOLUME_DEVIATION']
  - edge ['asset:unsw:192.168.1.240', 'asset:unsw:208.67.220.220'] score=0.3201727666264798 reasons=['FAN_OUT_DEVIATION', 'TRAFFIC_VOLUME_DEVIATION']
  - edge ['asset:unsw:192.168.1.240', 'asset:unsw:208.67.220.220'] score=0.3197660758696258 reasons=['FAN_OUT_DEVIATION', 'TRAFFIC_VOLUME_DEVIATION']
  - edge ['asset:unsw:192.168.1.240', 'asset:unsw:8.8.8.8'] score=0.31531481258485305 reasons=['FAN_OUT_DEVIATION', 'TRAFFIC_VOLUME_DEVIATION']
  - edge ['asset:unsw:192.168.1.240', 'asset:unsw:8.8.8.8'] score=0.31531481258485305 reasons=['FAN_OUT_DEVIATION', 'TRAFFIC_VOLUME_DEVIATION']

## episode:6f09bfa28d13ea0e541e (STRONG)
- assets: ['asset:unsw:192.168.1.240', 'asset:unsw:208.67.220.220', 'asset:unsw:8.8.8.8']
- relationships: ['rel:asset:unsw:192.168.1.240|asset:unsw:208.67.220.220|COMMUNICATES_WITH', 'rel:asset:unsw:192.168.1.240|asset:unsw:8.8.8.8|COMMUNICATES_WITH']
- evidence families: ['TOPOLOGY_SPREAD', 'PROTOCOL_CHANGE', 'PORT_CHANGE', 'TRAFFIC_VOLUME', 'DIRECTIONAL_CHANGE']
  - edge ['asset:unsw:192.168.1.240', 'asset:unsw:208.67.220.220'] score=0.31973838466335125 reasons=['FAN_OUT_DEVIATION', 'TRAFFIC_VOLUME_DEVIATION']
  - edge ['asset:unsw:192.168.1.240', 'asset:unsw:208.67.220.220'] score=0.32682727474564655 reasons=['FAN_OUT_DEVIATION', 'TRAFFIC_VOLUME_DEVIATION']
  - edge ['asset:unsw:192.168.1.240', 'asset:unsw:208.67.220.220'] score=0.3200831960530656 reasons=['FAN_OUT_DEVIATION', 'TRAFFIC_VOLUME_DEVIATION']
  - edge ['asset:unsw:192.168.1.240', 'asset:unsw:208.67.220.220'] score=0.3207531350330062 reasons=['FAN_OUT_DEVIATION', 'TRAFFIC_VOLUME_DEVIATION']
  - edge ['asset:unsw:192.168.1.240', 'asset:unsw:208.67.220.220'] score=0.3200831960530656 reasons=['FAN_OUT_DEVIATION', 'TRAFFIC_VOLUME_DEVIATION']
  - edge ['asset:unsw:192.168.1.240', 'asset:unsw:8.8.8.8'] score=0.3218344969186495 reasons=['FAN_OUT_DEVIATION', 'TRAFFIC_VOLUME_DEVIATION']
  - edge ['asset:unsw:192.168.1.240', 'asset:unsw:8.8.8.8'] score=0.32275114729168836 reasons=['FAN_OUT_DEVIATION', 'TRAFFIC_VOLUME_DEVIATION']
  - node ['asset:unsw:192.168.1.240'] score=0.863834777237287 reasons=['COMMUNICATION_RATIO_SHIFT', 'FAN_OUT_DEVIATION', 'OUTBOUND_VOLUME_DEVIATION', 'PORT_DIVERSITY_CHANGE', 'PROTOCOL_DIVERSITY_CHANGE']

