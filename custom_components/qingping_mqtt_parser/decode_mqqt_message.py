from .utils import parser
import logging
_LOGGER = logging.getLogger(__name__)

def decode(topic, payload):

    try:
        addr = topic.value.split('/')[1]
        data = parser.parse_data(payload)

        r = {
            "addr": addr,
            "data": data,
        }

        _LOGGER.info(r)

        return r
    except:
        return False