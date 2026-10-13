# Evidence Graph Examples (analysis only)

## episode:c95d75c2783c529a9df4 (STRONG)
- assets: ['asset:unsw:108.61.56.35', 'asset:unsw:129.250.35.251', 'asset:unsw:129.6.15.29', 'asset:unsw:162.213.2.253', 'asset:unsw:176.32.100.25', 'asset:unsw:176.32.101.122', 'asset:unsw:192.168.1.1', 'asset:unsw:192.168.1.240', 'asset:unsw:192.96.202.120', 'asset:unsw:204.9.54.119', 'asset:unsw:206.108.0.131', 'asset:unsw:207.171.178.6', 'asset:unsw:208.67.220.220', 'asset:unsw:208.75.89.4', 'asset:unsw:23.105.70.69', 'asset:unsw:23.23.189.20', 'asset:unsw:23.23.78.14', 'asset:unsw:68.32.10.103', 'asset:unsw:69.164.202.202', 'asset:unsw:72.21.207.82', 'asset:unsw:72.21.215.34', 'asset:unsw:8.8.8.8', 'asset:unsw:96.126.100.203', 'asset:unsw:96.126.105.86']
- relationships: ['rel:asset:unsw:192.168.1.240|asset:unsw:108.61.56.35|COMMUNICATES_WITH', 'rel:asset:unsw:192.168.1.240|asset:unsw:129.250.35.251|COMMUNICATES_WITH', 'rel:asset:unsw:192.168.1.240|asset:unsw:129.6.15.29|COMMUNICATES_WITH', 'rel:asset:unsw:192.168.1.240|asset:unsw:162.213.2.253|COMMUNICATES_WITH', 'rel:asset:unsw:192.168.1.240|asset:unsw:176.32.100.25|COMMUNICATES_WITH', 'rel:asset:unsw:192.168.1.240|asset:unsw:176.32.101.122|COMMUNICATES_WITH', 'rel:asset:unsw:192.168.1.240|asset:unsw:192.168.1.1|COMMUNICATES_WITH', 'rel:asset:unsw:192.168.1.240|asset:unsw:192.96.202.120|COMMUNICATES_WITH', 'rel:asset:unsw:192.168.1.240|asset:unsw:204.9.54.119|COMMUNICATES_WITH', 'rel:asset:unsw:192.168.1.240|asset:unsw:206.108.0.131|COMMUNICATES_WITH', 'rel:asset:unsw:192.168.1.240|asset:unsw:207.171.178.6|COMMUNICATES_WITH', 'rel:asset:unsw:192.168.1.240|asset:unsw:208.67.220.220|COMMUNICATES_WITH', 'rel:asset:unsw:192.168.1.240|asset:unsw:208.75.89.4|COMMUNICATES_WITH', 'rel:asset:unsw:192.168.1.240|asset:unsw:23.105.70.69|COMMUNICATES_WITH', 'rel:asset:unsw:192.168.1.240|asset:unsw:23.23.189.20|COMMUNICATES_WITH', 'rel:asset:unsw:192.168.1.240|asset:unsw:23.23.78.14|COMMUNICATES_WITH', 'rel:asset:unsw:192.168.1.240|asset:unsw:68.32.10.103|COMMUNICATES_WITH', 'rel:asset:unsw:192.168.1.240|asset:unsw:69.164.202.202|COMMUNICATES_WITH', 'rel:asset:unsw:192.168.1.240|asset:unsw:72.21.207.82|COMMUNICATES_WITH', 'rel:asset:unsw:192.168.1.240|asset:unsw:72.21.215.34|COMMUNICATES_WITH', 'rel:asset:unsw:192.168.1.240|asset:unsw:8.8.8.8|COMMUNICATES_WITH', 'rel:asset:unsw:192.168.1.240|asset:unsw:96.126.100.203|COMMUNICATES_WITH', 'rel:asset:unsw:192.168.1.240|asset:unsw:96.126.105.86|COMMUNICATES_WITH']
- evidence families: ['PEER_NOVELTY', 'TOPOLOGY_SPREAD', 'PROTOCOL_CHANGE', 'PORT_CHANGE', 'TRAFFIC_VOLUME', 'DIRECTIONAL_CHANGE', 'PEER_SET_CHANGE']
  - edge ['asset:unsw:108.61.56.35', 'asset:unsw:192.168.1.240'] score=0.7088707396209448 reasons=['APP_PROTOCOL_NOVELTY', 'FAN_OUT_DEVIATION', 'NEW_PEER', 'PORT_NOVELTY', 'PROTOCOL_NOVELTY']
  - edge ['asset:unsw:129.250.35.251', 'asset:unsw:192.168.1.240'] score=0.7167515011361116 reasons=['APP_PROTOCOL_NOVELTY', 'FAN_OUT_DEVIATION', 'NEW_PEER', 'PORT_NOVELTY', 'PROTOCOL_NOVELTY']
  - edge ['asset:unsw:129.6.15.29', 'asset:unsw:192.168.1.240'] score=0.730629263982444 reasons=['APP_PROTOCOL_NOVELTY', 'FAN_OUT_DEVIATION', 'NEW_PEER', 'PORT_NOVELTY', 'PROTOCOL_NOVELTY']
  - edge ['asset:unsw:162.213.2.253', 'asset:unsw:192.168.1.240'] score=0.7088707396209448 reasons=['APP_PROTOCOL_NOVELTY', 'FAN_OUT_DEVIATION', 'NEW_PEER', 'PORT_NOVELTY', 'PROTOCOL_NOVELTY']
  - edge ['asset:unsw:176.32.100.25', 'asset:unsw:192.168.1.240'] score=0.35871858400399914 reasons=['FAN_OUT_DEVIATION', 'TRAFFIC_VOLUME_DEVIATION']
  - edge ['asset:unsw:176.32.101.122', 'asset:unsw:192.168.1.240'] score=0.3402860058863248 reasons=['FAN_OUT_DEVIATION', 'TRAFFIC_VOLUME_DEVIATION']
  - edge ['asset:unsw:192.168.1.1', 'asset:unsw:192.168.1.240'] score=0.4219973011790865 reasons=['FAN_OUT_DEVIATION', 'PROTOCOL_NOVELTY', 'TRAFFIC_VOLUME_DEVIATION']
  - edge ['asset:unsw:192.168.1.1', 'asset:unsw:192.168.1.240'] score=0.4082337129258786 reasons=['FAN_OUT_DEVIATION', 'TRAFFIC_VOLUME_DEVIATION']

## episode:75dd1ce8221eeb2a9bc9 (STRONG)
- assets: ['asset:unsw:149.171.37.162', 'asset:unsw:192.168.1.1', 'asset:unsw:192.168.1.240', 'asset:unsw:208.67.220.220', 'asset:unsw:8.8.8.8']
- relationships: ['rel:asset:unsw:149.171.37.162|asset:unsw:192.168.1.240|COMMUNICATES_WITH', 'rel:asset:unsw:192.168.1.240|asset:unsw:192.168.1.1|COMMUNICATES_WITH', 'rel:asset:unsw:192.168.1.240|asset:unsw:208.67.220.220|COMMUNICATES_WITH', 'rel:asset:unsw:192.168.1.240|asset:unsw:8.8.8.8|COMMUNICATES_WITH']
- evidence families: ['PEER_NOVELTY', 'TOPOLOGY_SPREAD', 'PROTOCOL_CHANGE', 'PORT_CHANGE', 'TRAFFIC_VOLUME', 'DIRECTIONAL_CHANGE', 'PEER_SET_CHANGE']
  - edge ['asset:unsw:149.171.37.162', 'asset:unsw:192.168.1.240'] score=0.7106251872946725 reasons=['APP_PROTOCOL_NOVELTY', 'FAN_OUT_DEVIATION', 'NEW_PEER', 'PROTOCOL_NOVELTY', 'TRAFFIC_VOLUME_DEVIATION']
  - edge ['asset:unsw:192.168.1.1', 'asset:unsw:192.168.1.240'] score=0.3524929436435226 reasons=['FAN_OUT_DEVIATION', 'PROTOCOL_NOVELTY', 'TRAFFIC_VOLUME_DEVIATION']
  - edge ['asset:unsw:192.168.1.240', 'asset:unsw:208.67.220.220'] score=0.35982003287327974 reasons=['FAN_OUT_DEVIATION', 'PROTOCOL_NOVELTY', 'TRAFFIC_VOLUME_DEVIATION']
  - edge ['asset:unsw:192.168.1.240', 'asset:unsw:208.67.220.220'] score=0.3312240838455569 reasons=['FAN_OUT_DEVIATION', 'TRAFFIC_VOLUME_DEVIATION']
  - edge ['asset:unsw:192.168.1.240', 'asset:unsw:208.67.220.220'] score=0.3193966523864762 reasons=['FAN_OUT_DEVIATION', 'TRAFFIC_VOLUME_DEVIATION']
  - edge ['asset:unsw:192.168.1.240', 'asset:unsw:208.67.220.220'] score=0.32465521494120614 reasons=['FAN_OUT_DEVIATION', 'TRAFFIC_VOLUME_DEVIATION']
  - edge ['asset:unsw:192.168.1.240', 'asset:unsw:208.67.220.220'] score=0.3191336194073535 reasons=['FAN_OUT_DEVIATION', 'TRAFFIC_VOLUME_DEVIATION']
  - edge ['asset:unsw:192.168.1.240', 'asset:unsw:208.67.220.220'] score=0.33307651322236254 reasons=['FAN_OUT_DEVIATION', 'TRAFFIC_VOLUME_DEVIATION']

## episode:f0b020b9d8e3ed206cdd (STRONG)
- assets: ['asset:unsw:149.171.37.162', 'asset:unsw:192.168.1.1', 'asset:unsw:192.168.1.240', 'asset:unsw:208.67.220.220', 'asset:unsw:8.8.8.8']
- relationships: ['rel:asset:unsw:149.171.37.162|asset:unsw:192.168.1.240|COMMUNICATES_WITH', 'rel:asset:unsw:192.168.1.240|asset:unsw:192.168.1.1|COMMUNICATES_WITH', 'rel:asset:unsw:192.168.1.240|asset:unsw:208.67.220.220|COMMUNICATES_WITH', 'rel:asset:unsw:192.168.1.240|asset:unsw:8.8.8.8|COMMUNICATES_WITH']
- evidence families: ['TOPOLOGY_SPREAD', 'PROTOCOL_CHANGE', 'PORT_CHANGE', 'TRAFFIC_VOLUME', 'DIRECTIONAL_CHANGE']
  - edge ['asset:unsw:149.171.37.162', 'asset:unsw:192.168.1.240'] score=0.35319352049576075 reasons=['TRAFFIC_VOLUME_DEVIATION']
  - edge ['asset:unsw:192.168.1.1', 'asset:unsw:192.168.1.240'] score=0.35354707388660805 reasons=['FAN_OUT_DEVIATION', 'PROTOCOL_NOVELTY', 'TRAFFIC_VOLUME_DEVIATION']
  - edge ['asset:unsw:192.168.1.240', 'asset:unsw:208.67.220.220'] score=0.3488299734036341 reasons=['FAN_OUT_DEVIATION', 'PROTOCOL_NOVELTY', 'TRAFFIC_VOLUME_DEVIATION']
  - edge ['asset:unsw:192.168.1.240', 'asset:unsw:208.67.220.220'] score=0.32949620235764315 reasons=['FAN_OUT_DEVIATION', 'TRAFFIC_VOLUME_DEVIATION']
  - edge ['asset:unsw:192.168.1.240', 'asset:unsw:208.67.220.220'] score=0.3277287141405191 reasons=['FAN_OUT_DEVIATION', 'TRAFFIC_VOLUME_DEVIATION']
  - edge ['asset:unsw:192.168.1.240', 'asset:unsw:208.67.220.220'] score=0.31904403956898647 reasons=['FAN_OUT_DEVIATION', 'TRAFFIC_VOLUME_DEVIATION']
  - edge ['asset:unsw:192.168.1.240', 'asset:unsw:208.67.220.220'] score=0.3200831960530656 reasons=['FAN_OUT_DEVIATION', 'TRAFFIC_VOLUME_DEVIATION']
  - edge ['asset:unsw:192.168.1.240', 'asset:unsw:208.67.220.220'] score=0.3193003528481923 reasons=['FAN_OUT_DEVIATION', 'TRAFFIC_VOLUME_DEVIATION']

