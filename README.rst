A beatsqlalchemy project mod for CloudMl
===============================

A beatsqllchemy project.

This is a Celery Beat Scheduler (http://celery.readthedocs.org/en/latest/userguide/periodic-tasks.html)
that stores both the schedules themselves and their status
information in a backend SQLALChemy database. It can be installed by
installing the beatsqlalchemy Python egg::

    # pip install -U git+ssh://git@192.168.1.121/qtools/beatsqlalchemy.git

And specifying the scheduler when running Celery Beat, e.g.::

    $ celery beat -S beatsqlalchemy.schedulers.DatabaseScheduler

Settings for the scheduler are defined in your celery configuration file
similar to how other aspects of Celery are configured::

    ENGINE_URL = "mysql+mysqldb://root:letsg0@192.168.99.100:3307/celerybeat?charset=utf8"

If no settings are specified, the library will attempt to use the
**schedules** collection in the local **celery** database.

Schedules can be manipulated in the SQLALChemy database.There exist two types of schedules,
interval and crontab.


The following fields are required: name, task, crontab || interval,
enabled when defining new tasks.
total_run_count and last_run_at are maintained by the
scheduler and should not be externally manipulated.

The example from Celery User Guide::Periodic Tasks.
(see: http://docs.celeryproject.org/en/latest/userguide/periodic-tasks.html#crontab-schedules)::

	{

		CELERYBEAT_SCHEDULE = {
		    # Executes every Monday morning at 7:30 A.M
		    'add-every-monday-morning': {
		        'task': 'tasks.add',
		        'schedule': crontab(hour=7, minute=30, day_of_week=1),
		        'args': (16, 16),
		    },
		}
	}