from phoenix.otel import register
from config.setting import env
import requests

class Phoenix:
    
    @staticmethod
    def init():
        is_reachable = None
        if ( hasattr(env, 'phoenix_endpoint') 
            and hasattr(env, 'phoenix_api_key') 
            and env.PHOENIX_ENDPOINT 
            and env.PHOENIX_API_KEY
            ):
            is_reachable = False
        try:
            response = requests.get(env.PHOENIX_ENDPOINT, timeout=3)
            if response.status_code < 500: # Any non-server-error response
                is_reachable = True
            else:
                print(f"⚠️ Phoenix endpoint returned a server error: {response.status_code}.")

        except requests.exceptions.RequestException as e:
            print(f"❌ Phoenix endpoint is not reachable. Tracing disabled. Error: {type(e).__name__}")

        if is_reachable:
            register(
                project_name=env.APP_NAME,
                endpoint=env.PHOENIX_ENDPOINT,
                auto_instrument=True,
                batch=True,
                verbose=False,
                headers = {"Authorization": f"Bearer {env.PHOENIX_API_KEY}"}
            )

    @staticmethod
    def metadata():
        return {
            "service_version": env.APP_VERSION,
            "deployment_environment": env.APP_ENV,
        }
