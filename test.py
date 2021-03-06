#!/usr/bin/env python3
from networks import VRR
from models import Collection, Stop, Location, Trip, unserialize_typed
import json

collection = Collection('test')

vrr = VRR(collection)
bs = Stop(city='essen', name='fliegenbusch')
bo = Stop(city='essen', name='hbf')

trip = Trip.Request()
trip.origin = bs
trip.destination = bo

location = Location.Request()
location.name = 'Borbeck'

# result = vrr.search_trips(trip)

unserialize_typed

result, ids = vrr.query(bo, get_ids=True)

print(json.dumps(collection.get_by_ids_serialized(ids), indent=2))

stops = sorted(vrr.collection.known['Stop'], key=lambda s: s.name)

# for trip in result:
#    print(trip)
# result = vrr.get_stop_rides(bs)
# result = vrr.get_stop_rides(bo)
# p = PrettyPrint()
# print(p.formatted(result))
# result.serialize(typed=True)
serialized = result.serialize(typed=True, children_refer_by='test')
# unserialized = unserialize_typed(serialized)
# serialized2 = unserialized.serialize(typed=True)
# open('out1.json', 'w').write(json.dumps(serialized, indent=2, sort_keys=True))
# open('out2.json', 'w').write(json.dumps(serialized2, indent=2, sort_keys=True))
# print(serialized)
print(json.dumps(serialized, indent=2))
# print(json.dumps(vrr.collection.serialize(typed=True), indent=2))
