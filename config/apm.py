import requests
import json
from config.setting import env
from elasticapm.contrib.starlette import make_apm_client
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

class NullAPMClient:
    def __getattr__(self, name):
        return lambda *args, **kwargs: None 
    
    def __call__(self, *args, **kwargs):
        return self

class APM:
    def __init__(self, max_workers=5):
        self.enabled = str(env.ENABLE_APM).strip() == '1'
        if self.enabled:
            self.client = make_apm_client({
                'SERVICE_NAME': env.APM_SERVICE_NAME,
                'SERVER_URL': env.APM_SERVER_URL,
                'TRANSACTIONS_IGNORE_PATTERNS': '/ws*',
                'ENVIRONMENT': env.APP_ENV,
                'CAPTURE_BODY': 'all',
                'TRANSACTION_SAMPLE_RATE': 1.0,
                'SPAN_FRAMES_MIN_DURATION': '5ms',
                'DISABLE_LOG_RECORD_FACTORY': False, 
                'LOG_LEVEL': 'info',
                'AUTO_LOG_STACKS': False
            })
            self.apm_server_url = env.APM_SERVER_URL
            self.intake_url = f"{self.apm_server_url}/intake/v2/events"
            self.executor = ThreadPoolExecutor(
                max_workers=max_workers, 
                thread_name_prefix="apm_logger"
            )
            self._lock = Lock()
        else:
            print("APM is disabled via environment variable.")
            self.client = NullAPMClient() 
            self.executor = NullAPMClient()
            self.apm_server_url = ""
            self.intake_url = ""
            self._lock = NullAPMClient()
        
    def _send_log_sync(self, message, level="info", metadata=None):
        """Internal synchronous send (runs in background thread)"""
        metadata_payload = {
            "metadata": {
                "service": {
                    "name": env.APM_SERVICE_NAME,
                    "environment": env.APP_ENV,
                    "version": env.APP_VERSION,
                    "agent": {
                        "name": "python-logger-standalone",
                        "version": "1.0.0"
                    },
                    "language": {
                        "name": "python"
                    },
                }
            }
        }
        
        log_payload = {
            "log": {
                "message": message,
            }
        }
        payload = json.dumps(metadata_payload) + "\n" + json.dumps(log_payload) + "\n"
        
        try:
            response = requests.post(
                self.intake_url,
                data=payload,
                headers={
                    "Content-Type": "application/x-ndjson",
                    "Accept": "application/json"
                },
                timeout=30
            )
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            print(f"Failed to send log to APM: {e}")
            return None

    def send_log(self, message, level="info", **kwargs):
        """Non-blocking send - submits to thread pool and returns immediately"""
        if self.enabled:
            return self.executor.submit(self._send_log_sync, message, level, kwargs)
    
    def close(self, wait=True):
        """Shutdown the executor (call this on app close)"""
        if self.enabled:
            self.executor.shutdown(wait=wait)

apm = APM()
