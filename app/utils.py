import time
import logging
import os
from app import db
from app.models import ActivityLog
from flask import request

_logger = None

def get_audit_logger():
    global _logger
    if _logger is not None:
        return _logger
    _logger = logging.getLogger('app_audit')
    log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'security_audit.log')
    handler = logging.FileHandler(log_path, mode='a')
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    handler.setFormatter(formatter)
    _logger.addHandler(handler)
    _logger.setLevel(logging.INFO)
    _logger.propagate = False
    return _logger

def current_time_millis():
    return int(time.time() * 1000)

def log_activity(identifier, action):
    ip_addr = request.remote_addr if request else "Unknown"
    log_entry = ActivityLog(
        identifier=identifier,
        action=action,
        ip_address=ip_addr,
        timestamp=current_time_millis()
    )
    db.session.add(log_entry)
    db.session.commit()

def log_security_event(event, detail='', identifier='Anonymous', ip='Unknown'):
    logger = get_audit_logger()
    logger.warning(f'{event} | {detail} | User: {identifier} | IP: {ip}')
