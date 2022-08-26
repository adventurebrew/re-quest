import logging
import sys

import av

debug = False


def setup_logger():
    # pyav issues boring warnings...
    # disable according to https://github.com/PyAV-Org/PyAV/issues/711
    av.logging.set_level(av.logging.PANIC)

    logger = logging.getLogger('sounder')
    if debug:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)

    logger_handler = logging.StreamHandler()
    logger_handler.addFilter(lambda record: record.levelno != logging.INFO)
    logger_handler.setFormatter(logging.Formatter('%(levelname)s:%(name)s:%(message)s'))
    logger.addHandler(logger_handler)

    logger_info_handler = logging.StreamHandler(sys.stdout)
    logger_info_handler.addFilter(lambda record: record.levelno == logging.INFO)
    logger.addHandler(logger_info_handler)

    return logger


def read_le(stream, length=1):
    b = stream.read(length)
    if b == b'':
        logger.debug(f'read_le: {stream.tell()}\t EOF')
        raise EOFError
    return int.from_bytes(b, byteorder='little')


def read_be(stream, length=1):
    b = stream.read(length)
    if b == b'':
        logger.debug(f'read_be: {stream.tell()}\t EOF')
        raise EOFError
    return int.from_bytes(b, byteorder='big')


def write_le(stream, data, length=1):
    stream.write(data.to_bytes(length=length, byteorder='little'))


def get_all_channels(devices):
    result = []
    for device_channels in devices.values():
        for c in device_channels:
            if c.num != 'digital':
                result.append(c.num)
    return sorted(list(set(result)))


logger = setup_logger()
