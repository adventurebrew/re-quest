
import itertools
import os
import pathlib
from typing import Iterable, Optional, Union

RESOURCE_MAP_SUPPORTED = False
try:
    from . import sci0_resource
except ImportError:
    sci0_resource = None
else:
    RESOURCE_MAP_SUPPORTED = True


def load_resources(
    base_dir: Union[str, os.PathLike[str]],
    resmap: Optional[str] = 'RESOURCE.MAP',
    patches: Optional[Iterable[str]] = (),
    pattern: str = '*'
):
    """Dynamically load resources of SCI0 game in given base_dir, of given glob pattern
    First it tries to load from patches directory, ordered by priority, by default it only search the base directory
    If given None explicitly, it will skip loading files from directory completely
    Then, it tries loading archive files, by specifying resource map (resmap) for remaining files,
    default is RESOURCE.MAP, if given None explicitly it will skip loading files from archive.

    Usage example:
    ```
    for resource in load_resources(
        r"Path\To\Game\Conquests of Camelot",
        patches=['PATCHES'],
        pattern='vocab.*',
    ):
        name, data = resource.name, resource.read_bytes()
        do_something(name, data)
    ```

    """
    parsed_files = set()

    base_dir = pathlib.Path(base_dir)

    if patches is not None:
        for rp in itertools.chain(patches, ('.',)):
            patch_dir = base_dir / rp
            for entry in patch_dir.glob(pattern):
                if entry.name not in parsed_files:
                    parsed_files.add(entry.name)
                    yield entry

    if resmap is not None:
        if not RESOURCE_MAP_SUPPORTED:
            print('WARNING: Reading resources from RESOURCE.MAP is skipped because dependecies are missing')
            print('To enable it, please run the following command:\n  pip install git+https://github.com/adventurebrew/pakal.git')
            return

        with sci0_resource.open(base_dir / resmap) as archive:
            for entry in archive.glob(pattern):
                if entry.name not in parsed_files:
                    parsed_files.add(entry.name)
                    yield entry
