#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
#=============================================================================
#     FileName: schedulers
#         Desc:
#       Author: ge.jin
#        Email: ge.jin@woqutech.com
#     HomePage: wwww.woqutech.com
#      Version: 0.0.1
#   LastChange: 4/13/16 3:38 PM
#      History:
#=============================================================================
'''
import json
from multiprocessing.util import Finalize

from celery import current_app
from celery import schedules
from celery.beat import ScheduleEntry, Scheduler
from celery.utils.encoding import safe_str
from celery.utils.log import get_logger
from celery.utils.timeutils import is_naive
from model import PeriodicTask, CrontabSchedule, PeriodicTasks, get_session, IntervalSchedule

DEFAULT_MAX_INTERVAL = 5

ADD_ENTRY_ERROR = """\
Couldn't add entry %r to database schedule: %r. Contents: %r
"""

logger = get_logger(__name__)
debug, info, error = logger.debug, logger.info, logger.error


class ModelEntry(ScheduleEntry):
    model_schedules = ((schedules.crontab, CrontabSchedule, 'crontab'),
                       (schedules.schedule, IntervalSchedule, 'interval'))
    save_fields = ['last_run_at', 'total_run_count', 'no_changes']

    def __init__(self, model, session=None):
        self.app = current_app
        self.session = session or get_session()
        self.name = model.name
        self.task = model.task
        self.schedule = model.schedule
        self.args = json.loads(model.args or '[]')
        self.kwargs = json.loads(model.kwargs or '{}')
        self.total_run_count = model.total_run_count
        self.model = model
        self.options = {}  # need reconstruction
        if not model.last_run_at:
            model.last_run_at = self._default_now()
        orig = self.last_run_at = model.last_run_at
        if not is_naive(self.last_run_at):
            self.last_run_at = self.last_run_at.replace(tzinfo=None)
        assert orig.hour == self.last_run_at.hour  # timezone sanity

    def _disable(self, model):
        model.no_changes = True
        model.enabled = False
        self.session.add(model)

    def is_due(self):
        if not self.model.enabled:
            return False, 5.0   # 5 second delay for re-enable.
        return self.schedule.is_due(self.last_run_at)

    def _default_now(self):
        return self.app.now()

    def __next__(self):
        self.model.last_run_at = self.app.now()
        self.model.total_run_count += 1
        self.model.no_changes = True
        return self.__class__(self.model)

    next = __next__  # for 2to3

    def save(self):
        obj = PeriodicTask.filter_by(self.session, id=self.model.id).first()
        for field in self.save_fields:
            setattr(obj, field, getattr(self.model, field))
        self.save_model(self.session, obj)

    @staticmethod
    def save_model(session, obj):
        session.add(obj)

    @classmethod
    def to_model_schedule(cls, schedule, session):
        for schedule_type, model_type, model_field in cls.model_schedules:
            debug(cls.model_schedules)
            schedule = schedules.maybe_schedule(schedule)
            if isinstance(schedule, schedule_type):
                model_schedule = model_type.from_schedule(session, schedule)
                cls.save_model(session, model_schedule)
                return model_schedule, model_field
        raise ValueError('Cannot convert schedule type {0!r} to model'.format(schedule))

    @classmethod
    def from_entry(cls, name, session, skip_fields=('relative', 'options'), **entry):
        fields = dict(entry)
        for skip_field in skip_fields:
            fields.pop(skip_field, None)
        schedule = fields.pop('schedule')
        model_schedule, model_field = cls.to_model_schedule(schedule, session)
        fields[model_field] = model_schedule
        fields['args'] = json.dumps(fields.get('args') or [])
        fields['kwargs'] = json.dumps(fields.get('kwargs') or {})
        model, _ = PeriodicTask.update_or_create(session, name=name, defaults=fields)
        cls.save_model(session, model)
        return cls(model)

    def __repr__(self):
        return '<ModelEntry: {0} {1}(*{2}, **{3}) {{4}}>'.format(
            safe_str(self.name), self.task, self.args, self.kwargs, self.schedule,
        )


class DatabaseScheduler(Scheduler):
    sync_every = 5

    Entry = ModelEntry
    Model = PeriodicTask
    Changes = PeriodicTasks
    _schedule = None
    _last_timestamp = None
    _initial_read = False

    def __init__(self, session=None, *args, **kwargs):
        self.session = session or get_session()
        self._dirty = set()
        self._finalize = Finalize(self, self.sync, exitpriority=5)
        super(DatabaseScheduler, self).__init__(*args, **kwargs)
        self.max_interval = (kwargs.get('max_interval') or
                             self.app.conf.CELERYBEAT_MAX_LOOP_INTERVAL or
                             DEFAULT_MAX_INTERVAL)

    def setup_schedule(self):
        self.install_default_entries(self.schedule)
        self.update_from_dict(self.app.conf.CELERYBEAT_SCHEDULE)

    def all_as_schedule(self):
        debug('DatabaseScheduler: Fetching database schedule')
        s = {}
        for model in self.Model.filter_by(self.session, enabled=True).all():
            try:
                s[model.name] = self.Entry(model)
            except ValueError:
                pass
        return s

    def schedule_changed(self):
        last, ts = self._last_timestamp, self.Changes.last_change(self.session)
        try:
            if ts and ts > (last if last else ts):
                return True
        finally:
            self._last_timestamp = ts
        return False

    def reserve(self, entry):
        new_entry = Scheduler.reserve(self, entry)
        self._dirty.add(new_entry.name)
        return new_entry

    def sync(self):
        info('Writing entries...')
        _tried = set()
        while self._dirty:
            try:
                name = self._dirty.pop()
                _tried.add(name)
                self.schedule[name].save()
            except KeyError:
                error("sync key error ")

    def update_from_dict(self, dict_):
        s = {}
        for name, entry in dict_.items():
            try:
                s[name] = self.Entry.from_entry(name, self.session, **entry)
            except Exception as exc:
                error(ADD_ENTRY_ERROR, name, exc, entry)
        self.schedule.update(s)

    def install_default_entries(self, data):
        entries = {}
        if self.app.conf.CELERY_TASK_RESULT_EXPIRES:
            entries.setdefault(
                'celery.backend_cleanup', {
                    'task': 'celery.backend_cleanup',
                    'schedule': schedules.crontab('*/5', '*', '*'),
                    'options': {'expires': 12 * 3600},
                },
            )
        self.update_from_dict(entries)

    @property
    def schedule(self):
        update = False
        if not self._initial_read:
            debug('DatabaseScheduler: intial read')
            update = True
            self._initial_read = True
        elif self.schedule_changed():
            debug('DatabaseScheduler: Schedule changed.')
            update = True

        if update:
            self.sync()
            self._schedule = self.all_as_schedule()
            debug('Current schedule:\n%s', '\n'.join(repr(entry) for entry in self._schedule.itervalues()))
        return self._schedule
