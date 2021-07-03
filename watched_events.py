from enum import Enum

class ITEM(str, Enum):
    ADDED = 'item:added'
    UPDATED = 'item:updated'
    COMPLETED = 'item:completed'
    UNCOMPLETED = 'item:uncompleted'
    DELETED = "item:deleted"

class NOTE(str, Enum):
    ADDED = 'note:added'
    UPDATED = 'note:updated'
    DELETED = 'note:deleted'

class PROJECT(str, Enum):
    ADDED = 'project:added'
    UPDATED = 'project:updated'
    DELETED = 'project:deleted'
    ARCHIVED = 'project:archived'
    UNARCHIVED = 'project:unarchived'

class LABEL(str, Enum):
    ADDED = 'label:added'
    UPDATED = 'label:updated'
    DELETED = 'label:deleted'

class FILTER(str, Enum):
    ADDED = 'filter:added'
    UPDATED = 'filter:updated'
    DELETED = 'filter:deleted'

class REMINDER(str, Enum):
    FIRED = 'reminder:fired'