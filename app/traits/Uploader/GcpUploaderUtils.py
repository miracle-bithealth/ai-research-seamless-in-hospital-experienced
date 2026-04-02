import io
from google.cloud import storage

class GcpUloader:
    """
    A class to handle file uploads to Google Cloud Storage.
    It manages the GCS client, authentication, and provides a core upload method.
    """
    def __init__(self, project_name: str, bucket_name: str, credentials):
        """
        Initializes the GCS client directly with configuration parameters.

        Args:
            project_name (str): The GCP project ID.
            bucket_name (str): The name of the GCS bucket to upload to.
            credentials_path (str): Path to the GCP service account JSON file.
        """
        self.project_name = project_name
        self.bucket_name = bucket_name
        self._client = storage.Client(project=self.project_name, credentials=credentials)
        self._bucket = self._client.get_bucket(self.bucket_name)

    async def upload_bytes(
        self, 
        file_bytes: bytes, 
        blob_path: str, 
        content_type: str
    ):
        """
        Core method to upload bytes to a specified GCS path.

        Args:
            file_bytes (bytes): The raw bytes of the file to upload.
            blob_path (str): The full destination path within the bucket (e.g., "audios/2025-08-27/file.wav").
            content_type (str): The MIME type of the file (e.g., "audio/wav").
        """
        try:
            blob = self._bucket.blob(blob_path)
            file_obj = io.BytesIO(file_bytes)
            blob.upload_from_file(file_obj, content_type=content_type)
            return blob.public_url
        except Exception as e:
            print(f"Error uploading to GCS: {e}")
            raise
