from contextlib import contextmanager
from typing import Any, Iterator, TypeVar

from pakal.archive import BaseArchive

from . import sci0_resource, sci1_resource

ArchiveType = TypeVar('ArchiveType', bound=BaseArchive)

@contextmanager
def open(*args: Any, **kwargs: Any) -> Iterator[ArchiveType]:
    try:
        with sci0_resource.open(*args, **kwargs) as inst:
            yield inst
    except:
        with sci1_resource.open(*args, **kwargs) as inst:
            yield inst
