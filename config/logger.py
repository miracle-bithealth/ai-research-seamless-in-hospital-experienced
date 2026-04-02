import sys
import logging
import json
from config.setting import env
from config.apm import APM, apm

class LoggerConfig:
    def __init__(self, apm_client: APM):
        self.apm = apm_client

    class CustomAPMLogHandler(logging.Handler):
        def __init__(self, apm_class: APM):
            super().__init__()
            self.apm_class = apm_class

        def emit(self, record: logging.LogRecord):
            try:
                msg = self.format(record)
                level = record.levelname.lower()
                self.apm_class.send_log(msg, level=level)
            except Exception:
                self.handleError(record)

    class MaxLevelFilter(logging.Filter):
        def __init__(self, max_level):
            super().__init__()
            self.max_level = max_level

        def filter(self, record: logging.LogRecord):
            return record.levelno < self.max_level
        
    class JsonFormatter(logging.Formatter):
        def format(self, record: logging.LogRecord) -> str:
            log_object = {
                "module": record.module,
                "func_name": record.funcName,
                "line_no": record.lineno,
            }
            if hasattr(record, 'extra_data'):
                log_object['extra_data'] = record.extra_data
            
            if record.exc_info:
                log_object['exc_info'] = self.formatException(record.exc_info)

            # Updated to use log_object logic or keep your custom string format
            final = (
                record.levelname.upper() + f" - {record.getMessage()} | " + 
                ((json.dumps(record.extra_data) + " | " ) if hasattr(record, 'extra_data') else "") +
                f"{record.module}.{record.funcName}:{record.lineno}"
            )
            return (final)

    def get_logger(self):
        logger = logging.getLogger()
        logger.setLevel("INFO")

        if logger.hasHandlers():
            logger.handlers.clear()

        if env.APP_ENV == "local":
            handler = logging.StreamHandler(sys.stdout)
            logger.addHandler(handler)

        if env.APM_SERVER_URL:
            custom_handler = self.CustomAPMLogHandler(apm_class=self.apm)
            custom_handler.setLevel(logging.INFO)
            custom_handler.setFormatter(self.JsonFormatter())
            logger.addHandler(custom_handler)
        
        return logger

logger = LoggerConfig(apm).get_logger()