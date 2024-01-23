import logging
import datetime
import pytz

class UTC7Formatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        utc7_time = datetime.datetime.fromtimestamp(record.created, pytz.timezone('Asia/Bangkok'))
        formatted_time = utc7_time.strftime('%Y-%m-%d %H:%M:%S')
        return formatted_time

def setup_logging(logger_name, log_file_path=None, logging_mode='both'):
    """
    Set up logging for a Python script.

    This function creates and configures a logger with the specified name and
    adds handlers according to the specified logging mode.

    Args:
        logger_name (str): The name of the logger.
        log_file_path (str, optional): The path to the log file. Used if logging to file.
        logging_mode (str, optional): The logging mode. Can be 'file', 'console', or 'both'. Default 'both'

    Returns:
        logging.Logger: The configured logger instance.
    """
    # Validate logging_mode
    valid_modes = ['file', 'console', 'both']
    if logging_mode not in valid_modes:
        # Default to console logging and log a warning
        logging_mode = 'console'

    # Handle missing file path when file logging is requested
    if logging_mode in ['file', 'both'] and not log_file_path:
        # Default to console logging and log a warning
        logging_mode = 'console'

    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)
    formatter = UTC7Formatter('%(asctime)s - [%(name)s.%(funcName)s] - %(levelname)s - %(message)s')

    # Do not add if there is existed handlers
    if not logger.handlers:
        if logging_mode in ['file', 'both'] and log_file_path:
            file_handler = logging.FileHandler(log_file_path)
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

        if logging_mode in ['console', 'both']:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)

    return logger

