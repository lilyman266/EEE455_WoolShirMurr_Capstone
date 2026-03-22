import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional


class LoggerFactory:
    #a logger factory, can write to the same log from different files.
    _loggers = {}
    _log_dir = Path("logs")
    _log_dir.mkdir(exist_ok=True)

    @staticmethod
    def get_logger(
        name: str,
        level: int = logging.INFO,
        log_to_file: bool = True,
        max_bytes: int = 5_000_000,
        backup_count: int = 5,
    ) -> logging.Logger:

        #Retrieve a logger by name. If it doesn't exist, create it.
        if name in LoggerFactory._loggers:
            return LoggerFactory._loggers[name]

        logger = logging.getLogger(name)
        logger.setLevel(level)
        logger.propagate = False  # Avoid double logging to root

        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        #Console Handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        #File Handler
        if log_to_file:
            file_path = LoggerFactory._log_dir / f"{name}.log"
            file_handler = RotatingFileHandler(
                file_path,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding="utf-8",
            )
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

        LoggerFactory._loggers[name] = logger
        return logger
