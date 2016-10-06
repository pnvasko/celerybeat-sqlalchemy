#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
#=============================================================================
#     FileName: base
#         Desc:
#       Author: ge.jin
#        Email: ge.jin@woqutech.com
#     HomePage: wwww.woqutech.com
#      Version: 0.0.1
#   LastChange: 4/28/16 9:31 AM
#      History:
#=============================================================================
'''
from datetime import datetime
from sqlalchemy import Column, Integer, DateTime
from sqlalchemy.ext.declarative import declarative_base


class TimestampModel(object):
    """
    自带两个时间戳字段的base model
    """
    id = Column(Integer, primary_key=True, autoincrement=True)
    create_time = Column(DateTime, default=datetime.utcnow)
    update_time = Column(DateTime, onupdate=datetime.utcnow)
    utc_fresh_time = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, doc="刷新时间utc")
    mysql_charset = 'utf8'

    @classmethod
    def filter_by(cls, session, **kwargs):
        """
        session.query(MyClass).filter_by(name = 'some name')
        :param kwargs:
        :param session:
        """
        return session.query(cls).filter_by(**kwargs)

    @classmethod
    def get_or_create(cls, session_obj, defaults=None, **kwargs):
        obj = session_obj.query(cls).filter_by(**kwargs).first()
        if obj:
            return obj, False
        else:
            params = dict((k, v) for k, v in kwargs.iteritems())
            params.update(defaults or {})
            obj = cls(**params)
            return obj, True

    @classmethod
    def update_or_create(cls, session_obj, defaults=None, **kwargs):
        obj = session_obj.query(cls).filter_by(**kwargs).first()
        if obj:
            for key, value in defaults.iteritems():
                setattr(obj, key, value)
            created = False
        else:
            params = dict((k, v) for k, v in kwargs.iteritems())
            params.update(defaults or {})
            obj = cls(**params)
            created = True
        return obj, created

Base = declarative_base(cls=TimestampModel)
