#!/usr/bin/env python3
from collections import Iterable, OrderedDict
from datetime import timedelta, datetime
import copy


class Serializable:
    def validate(self):
        myname = self.__class__._serialized_name()
        for c in self.__class__.__mro__:
            if not hasattr(c, '_validate'):
                continue

            added = ('(%s)' % c._serialized_name()) if c != self.__class__ else ''

            for name, allowed in c._validate():
                if not hasattr(self, name):
                    raise AttributeError('%s%s.%s is missing' % (myname, added, name))

                val = getattr(self, name)

                if allowed is None:
                    if val is not None and not isinstance(val, Iterable) and self.__class__.__name__ != 'RideSegment':
                        raise ValueError('%s%s.%s has non-iterable value: %s' % (myname, added, name, repr(getattr(self, name))))
                    if not c._validate_custom(self, name, val):
                        raise ValueError('%s%s.%s has invalid complex value: %s' % (myname, added, name, repr(getattr(self, name))))
                    continue

                if type(allowed) != tuple:
                    allowed = (allowed, )

                for a in allowed:
                    if a is None:
                        if val is None:
                            break
                    elif isinstance(val, a):
                        break
                else:
                    raise ValueError('%s%s.%s has to be %s, not %s' % (myname, added, name, self._validate_or(allowed), repr(getattr(self, name))))
        return True

    def _validate_or(self, items):
        if type(items) != tuple:
            return items.__name__
        out = []
        for item in items:
            if item is None:
                out.append('None')
            elif type(item) is tuple:
                out.append('Iterable(%s)' % self._validate_or(item))
            else:
                out.append(item.__name__)

        out = [(', ' + o) for o in out]
        if len(out) > 1:
            out[-1] = ' or ' + out[-1][2:]
        return ''.join(out)[2:]

    def _unserialize_typed(self, data, types=None):
        type_, data = data
        for t in types:
            if t._serialized_name() == type_:
                return t.unserialize(data)
        raise TypeError('Wrong datatype for unserialization')

    @classmethod
    def _unfold_subclasses(cls, allowed):
        if type(allowed) is not tuple:
            allowed = (allowed, )

        l = 0
        while len(allowed) != l:
            l = len(allowed)
            for a in allowed[:]:
                if a is not None and issubclass(a, Serializable):
                    allowed = tuple(set(allowed + tuple(a.__subclasses__())))
        return allowed

    def serialize(self, typed=False, **kwargs):
        refer_by = kwargs.get('refer_by')
        if refer_by is not None:
            if isinstance(self, Collectable) and refer_by in self._ids:
                if typed:
                    return self.__class__._serialized_name(), self._ids[refer_by]
                else:
                    return self._ids[refer_by]
        else:
            kwargs['refer_by'] = kwargs.get('children_refer_by')

        self.validate()
        data = OrderedDict()

        nostopresults = kwargs.get('nostopresults')

        if hasattr(self, '_serialize'):
            data = self._serialize()
        else:
            for c in self.__class__.__mro__:
                if not hasattr(c, '_validate'):
                    continue

                parent = c.__bases__[0]
                if hasattr(parent, '_validate') and parent._validate == c._validate:
                    continue

                for name, allowed in c._validate():
                    value = getattr(self, name)

                    if allowed is None:
                        n, v = c._serialize_custom(self, name, **kwargs)
                        if v is not None:
                            data[n] = v
                        continue

                    allowed = c._unfold_subclasses(allowed)
                    if c.__name__ == 'Stop' and isinstance(value, Searchable.Results):
                        if nostopresults is True:
                            continue
                        kwargs['nostopresults'] = True

                    if len(allowed) == 1:
                        if isinstance(value, Serializable):
                            value = value.serialize(**kwargs)
                        elif isinstance(value, datetime):
                            value = value.strftime('%Y-%m-%d %H:%M:%S')
                        elif isinstance(value, timedelta):
                            value = int(value.total_seconds())
                    else:
                        if value is None:
                            continue

                        if isinstance(value, Serializable):
                            t = len([a for a in allowed if a is not None and issubclass(a, Serializable)]) > 1
                            value = value.serialize(typed=t, **kwargs)
                        elif isinstance(value, datetime):
                            value = value.strftime('%Y-%m-%d %H:%M:%S')

                    if isinstance(value, timedelta):
                        value = value.total_seconds()
                    data[name] = value

        if typed:
            return self.__class__._serialized_name(), data
        else:
            return data

    @classmethod
    def _serialized_name(cls):
        if hasattr(cls, 'Model'):
            return cls.Model.__name__ + '.' + cls.__name__
        else:
            return cls.__name__

    def __ne__(self, other):
        return not (self == other)

    @classmethod
    def unserialize(cls, data):
        obj = cls()
        if hasattr(obj, '_unserialize'):
            obj._unserialize(data)
        else:
            for c in cls.__mro__:
                validate = {}
                if hasattr(c, '_validate'):
                    parent = c.__bases__[0]
                    if not hasattr(parent, '_validate') or parent._validate != c._validate:
                        validate = dict(c._validate())

                custom = hasattr(c, '_unserialize_custom')

                if not validate and not custom:
                    continue

                for name, value in data.items():
                    if name in validate and validate[name] is not None:
                        allowed = validate[name]

                        allowed = cls._unfold_subclasses(allowed)

                        if len(allowed) == 1:
                            if issubclass(allowed[0], Serializable):
                                value = allowed[0].unserialize(value)
                            elif issubclass(allowed[0], datetime):
                                value = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
                            elif issubclass(allowed[0], timedelta):
                                value = timedelta(seconds=value)
                        elif value is not None:
                            serializables = [a for a in allowed if a is not None and issubclass(a, Serializable)]
                            typed = len(serializables) > 1
                            if typed:
                                value = obj._unserialize_typed(value, serializables)
                            elif serializables:
                                value = serializables[0].unserialize(value)
                        setattr(obj, name, value)

                for name, value in data.items():
                    if (name not in validate or validate[name] is None) and custom:
                        c._unserialize_custom(obj, name, value)

        return obj

    def _update_collect(self, collection, last_update=None, ids=None):
        if last_update is not None and isinstance(self, Updateable):
            self.last_update = last_update

        newself = self
        if isinstance(self, Collectable):
            newself = collection.add(self)
            if ids is not None and collection.name:
                model = self.__class__._serialized_name()
                myid = newself._ids.get(collection.name)
                if myid is not None:
                    if model not in ids:
                        ids[model] = set()

                    ids[model].add(myid)

        if self is newself:
            self._collect_children(collection, last_update, ids=ids)
        return newself

    def _collect_children(self, collection, last_update=None, ids=None):
        for c in self.__class__.__mro__:
            if not hasattr(c, '_validate'):
                continue

            parent = c.__bases__[0]
            if hasattr(parent, '_validate') and parent._validate == c._validate:
                continue

            for name, allowed in c._validate():
                value = getattr(self, name)

                if isinstance(value, Serializable):
                    newvalue = value._update_collect(collection, last_update, ids=ids)

                    if isinstance(value, Collectable):
                        if newvalue is not value:
                            setattr(self, name, newvalue)


class Updateable(Serializable):
    @staticmethod
    def _validate():
        return (
            ('last_update', (datetime, None)),
            ('low_quality', (bool, None)),
        )

    def __init__(self):
        self.last_update = None
        self.low_quality = None

    def update(self, other):
        better = (other.last_update and self.last_update and other.last_update > self.last_update and (not other.low_quality or self.low_quality)) or (not other.low_quality and self.low_quality)

        if not self.last_update or better:
            self.last_update = other.last_update
            self.low_quality = other.low_quality

        for c in self.__class__.__mro__:
            if hasattr(c, '_update_default'):
                for name in c._update_default:
                    if getattr(self, name) is None or (better and getattr(other, name) is not None):
                        setattr(self, name, getattr(other, name))

            if hasattr(c, '_update'):
                c._update(self, other, better)

        for name, value in other._ids.items():
            if name in self._ids and type(value) == tuple and None in value:
                continue
            self._ids[name] = value


class MetaSearchable(type):
    def __init__(cls, a, b, c):
        cls.Request.Model = cls
        cls.Results.Model = cls
        cls.Results.content = cls


class Searchable(Updateable, metaclass=MetaSearchable):
    @staticmethod
    def _validate():
        return ()

    def matches(self, request):
        if not isinstance(request, Searchable.Request):
            raise TypeError('not a request')
        return request.matches(self)

    class Request(Updateable):
        def __init__(self):
            super().__init__()
            self.limit = None

        @staticmethod
        def _validate():
            return (
                ('limit', int),
            )

        def matches(self, obj):
            if not isinstance(obj, self.Model):
                raise TypeError('%s.Request can only match %s' % (self.Model.__name__, self.Model.__name__))
            obj.validate()
            return self._matches(obj)

        def _matches(self, obj):
            pass

    class Results(Updateable):
        def __init__(self, results=[], scored=False):
            super().__init__()
            if scored:
                self.results = list(results)
            else:
                self.results = [(r, None) for r in results]

        @staticmethod
        def _validate():
            return (
                ('results', None),
            )

        def _collect_children(self, collection, last_update=None, ids=None):
            super()._collect_children(collection, last_update, ids=ids)
            for i in range(len(self.results)):
                r = self.results[i]
                self.results[i] = (r[0]._update_collect(collection, last_update, ids=ids), r[1])

        def _validate_custom(self, name, value):
            if name == 'results':
                type_ = self.content
                for v in value:
                    if type(v) != tuple or len(v) != 2 or not isinstance(v[0], type_):
                        return False
                return True

        def _serialize_custom(self, name, **kwargs):
            if name == 'results':
                typed = len(self._unfold_subclasses(self.Model)) > 0
                return 'results', [(r[0].serialize(typed=typed, **kwargs), r[1]) for r in self.results]

        def _unserialize_custom(self, name, data):

            if name == 'results':
                possibilities = self._unfold_subclasses(self.Model)
                typed = len(possibilities) > 1
                if typed:
                    self.results = [(self._unserialize_typed(d[0], possibilities), d[1]) for d in data]
                else:
                    self.results = [(self.Model.unserialize(d[0]), d[1]) for d in data]

        def filter(self, request):
            if not self.results:
                return

            if not isinstance(request, self.Model.Request):
                raise TypeError('%s.Results can be filtered with %s' % (self.Model.__name__, self.Model.__name__))

            self.results = [r for r in self.results if request.matches(r)]

        def filtered(self, request):
            obj = copy.copy(self)
            obj.filter(request)
            return obj

        def __iter__(self):
            yield from (r[0] for r in self.results)

        def __len__(self):
            return len(self.results)

        def scored(self):
            yield from self.results

        def append(self, obj, score=None):
            self.results.append((obj, score))

        def _update(self, obj, better):
            for o in obj:
                for myo in self:
                    if o == myo:
                        myo.update(o)
                        break
                else:
                    self.append(myo)

        def __getitem__(self, key):
            return self.results[key]


class Collectable(Searchable):
    @staticmethod
    def _validate():
        return (
            ('_ids', None),
        )

    def __init__(self):
        super().__init__()
        self._ids = {}

    def _validate_custom(self, name, value):
        if name == '_ids':
            if not isinstance(value, dict):
                return False

            for name, data in value.items():
                if not isinstance(name, str):
                    return False

                if not isinstance(data, (int, str, tuple)):
                    return False
            return True

    def _equal_by_id(self, other):
        for name, value in self._ids.items():
            other_id = other._ids.get(name)
            if other_id is None:
                continue
            else:
                return value == other_id

    def _serialize_custom(self, name, **kwargs):
        if name == '_ids':
            return 'ids', self._ids

    def _unserialize_custom(self, name, data):
        if name == 'ids':
            for name, value in data.items():
                self._ids[name] = tuple(value) if isinstance(value, list) else value


class TripPart(Serializable):
    pass
